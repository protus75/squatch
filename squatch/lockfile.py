"""Single-writer lockfile (SQUATCH_PLAN.md D2, sections 6 and 15).

One advisory `flock` on `<state_dir>/squatch.lock` fences the orchestration
write surfaces -- ref mutation, commits, the journal, dispatch state -- against
a second daemon or a chat session. `flock` over an `O_EXCL` pidfile because it
needs no liveness protocol: the kernel drops the lock when the holder dies, so
a crashed daemon's lock is free at restart with no stale-pid reclaim. The file
body records the holder for diagnostics and the "someone else holds it" error;
correctness comes from the flock alone, never from those fields.
"""

import fcntl
import json
import os
import socket
from dataclasses import asdict, dataclass
from pathlib import Path

from squatch.seams import Clock

LOCK_NAME = "squatch.lock"


@dataclass(frozen=True)
class Holder:
    instance_id: str
    pid: int
    host: str
    state_dir: str
    started_at: str


class LockHeld(Exception):
    """The lock is already held. `holder` is the record the holder wrote, or
    None when it was unreadable (mid-write, foreign writer); the refusal
    stands either way."""

    def __init__(self, path: Path, holder: Holder | None):
        self.path = path
        self.holder = holder
        who = (f"{holder.instance_id} (pid {holder.pid} on {holder.host}, "
               f"since {holder.started_at})" if holder else "an unidentified holder")
        super().__init__(f"{path} is held by {who}")


class Lockfile:
    def __init__(self, state_dir: Path, *, instance_id: str, clock: Clock):
        if not isinstance(instance_id, str) or not instance_id:
            raise ValueError("instance_id must be a non-empty string")
        self._state_dir = Path(state_dir)
        self._instance_id = instance_id
        self._clock = clock
        self._fd: int | None = None

    @property
    def path(self) -> Path:
        return self._state_dir / LOCK_NAME

    @property
    def held(self) -> bool:
        return self._fd is not None

    def acquire(self) -> None:
        if self._fd is not None:
            raise LockHeld(self.path, self._read_holder())
        self._state_dir.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            raise LockHeld(self.path, self._read_holder()) from None
        except BaseException:
            os.close(fd)
            raise
        # The record is written in place through the locked descriptor, never
        # via the filesystem seam's temp-and-rename: the flock lives on this
        # inode, and a rename would swap in a fresh, unlocked one.
        holder = Holder(instance_id=self._instance_id, pid=os.getpid(),
                        host=socket.gethostname(), state_dir=str(self._state_dir),
                        started_at=self._clock().isoformat())
        os.ftruncate(fd, 0)
        os.write(fd, json.dumps(asdict(holder)).encode())
        self._fd = fd

    def release(self) -> None:
        if self._fd is None:
            raise RuntimeError(f"{self.path} is not held by this instance")
        # Never unlink: another process may already hold a descriptor to this
        # inode, and a fresh file would let two holders lock different inodes.
        fcntl.flock(self._fd, fcntl.LOCK_UN)
        os.close(self._fd)
        self._fd = None

    def _read_holder(self) -> Holder | None:
        try:
            return Holder(**json.loads(self.path.read_text()))
        except (OSError, ValueError, TypeError):
            return None

    def __enter__(self) -> "Lockfile":
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()
