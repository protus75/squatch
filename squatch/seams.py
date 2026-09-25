"""Injectable seams (SQUATCH_PLAN.md section 15).

Engine code never calls the clock, spawns a process, or writes a file raw; it
goes through one of these so a test can drive a fake. Each seam is the
minimal shape its consumers need and grows only with a consumer.
"""

import asyncio
import os
import signal
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Protocol

# One clock convention kernel-wide: a zero-arg callable returning an aware
# datetime, not a `now()` Protocol.
Clock = Callable[[], datetime]


class ProcessExec(Protocol):
    async def run(self, argv: Sequence[str], *, cwd: Path, env: Mapping[str, str],
                  timeout: float | None, stdin_path: Path | None = None,
                  on_spawn: Callable[[int], None] | None = None,
                  ) -> tuple[int, str, str]:
        """Spawn argv (never a shell) and return (rc, out, err). `on_spawn` is
        the spawn-time pgid hook: called with the child's process-group id
        the moment it exists, so a synchronous kill seam (`abort_current`)
        can target it while `run` is still awaiting."""
        ...


class Filesystem(Protocol):
    def write(self, path: Path, data: bytes) -> None:
        """Atomic write: temp file, fsync, rename."""
        ...

    def replace(self, src: Path, dst: Path) -> None:
        """Atomic rename of src over dst."""
        ...

    def unlink(self, path: Path) -> None:
        """Remove one file."""
        ...


class ExecutableNotFound(Exception):
    """argv[0] did not resolve; the seam's declared error, never an escaping
    FileNotFoundError."""


def kill_group(pgid: int) -> None:
    """Synchronous SIGKILL of a whole process group (signal, not reap)."""
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass


class SubprocessExec:
    """The production ProcessExec: asyncio subprocesses, never a shell.

    Every child gets its own process group so a timeout or cancellation kills
    the child AND whatever it spawned; killing only the direct child leaves
    grandchildren writing the worktree. `timeout=None` is the unbounded
    inherited-stdio mode (the self-upgrade handoff child): out/err are empty.
    """

    async def run(self, argv: Sequence[str], *, cwd: Path, env: Mapping[str, str],
                  timeout: float | None, stdin_path: Path | None = None,
                  on_spawn: Callable[[int], None] | None = None,
                  ) -> tuple[int, str, str]:
        capture = timeout is not None
        pipe = asyncio.subprocess.PIPE if capture else None
        stdin = open(stdin_path, "rb") if stdin_path is not None else asyncio.subprocess.DEVNULL
        try:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *argv, cwd=cwd, env=dict(env), stdin=stdin, stdout=pipe, stderr=pipe,
                    start_new_session=True)
            except FileNotFoundError as e:
                raise ExecutableNotFound(argv[0]) from e
        finally:
            if stdin_path is not None:
                stdin.close()
        if on_spawn is not None:
            on_spawn(proc.pid)  # start_new_session makes the pid the pgid
        try:
            async with asyncio.timeout(timeout):
                out, err = await proc.communicate()
        except (TimeoutError, asyncio.CancelledError):
            # One kill-and-wait path for both the seam's timeout and an outer
            # cancellation unwinding through here.
            await _kill_and_wait(proc)
            raise
        return (proc.returncode,
                out.decode(errors="replace") if capture else "",
                err.decode(errors="replace") if capture else "")


async def _kill_and_wait(proc: asyncio.subprocess.Process) -> None:
    kill_group(proc.pid)  # start_new_session makes the pid the pgid
    await proc.wait()


class LocalFilesystem:
    """The production Filesystem: temp file, fsync, rename."""

    def write(self, path: Path, data: bytes) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.tmp")
        with tmp.open("wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)

    def replace(self, src: Path, dst: Path) -> None:
        os.replace(src, dst)

    def unlink(self, path: Path) -> None:
        os.unlink(path)
