"""Injectable seams (SQUATCH_PLAN.md section 15).

Engine code never calls the clock, spawns a process, or writes a file raw; it
goes through one of these so a test can drive a fake. Each seam is the
minimal shape its consumers need and grows only with a consumer.
"""

import asyncio
import os
import signal
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Protocol

# One clock convention kernel-wide: a zero-arg callable returning an aware
# datetime, not a `now()` Protocol.
Clock = Callable[[], datetime]
Sleep = Callable[[float], Awaitable[None]]


class ProcessExec(Protocol):
    async def run(self, argv: Sequence[str], *, cwd: Path, env: Mapping[str, str],
                  timeout: float | None, stdin_path: Path | None = None,
                  on_spawn: Callable[[int], None] | None = None,
                  on_stdout_line: Callable[[str], None] | None = None,
                  ) -> tuple[int, str, str]:
        """Spawn argv (never a shell) and return (rc, out, err). `on_spawn` is
        the spawn-time pgid hook: called with the child's process-group id
        the moment it exists, so a synchronous kill seam (`abort_current`)
        can target it while `run` is still awaiting. When capture is active,
        `on_stdout_line` receives each decoded stdout line without its line
        ending as it arrives; stdout capture remains complete and unchanged."""
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

    def publish(self, path: Path, data: bytes) -> None:
        """Durably publish a whole file without replacing an existing path."""
        ...

    def read(self, path: Path) -> bytes:
        """Read one whole file."""
        ...

    def list(self, directory: Path, pattern: str) -> tuple[Path, ...]:
        """Return matching paths in stable name order."""
        ...

    def remove(self, path: Path) -> None:
        """Durably remove one file."""
        ...


class Notifications(Protocol):
    async def notify(self, argv: Sequence[str]) -> None:
        """Deliver argv, raising ExecutableNotFound or RuntimeError on failure."""
        ...


class SubprocessNotifications:
    """Notification children never share the active-work executor."""

    def __init__(self, *, cwd: Path, env: Mapping[str, str], timeout: float = 30) -> None:
        self._process = SubprocessExec()
        self._cwd = cwd
        self._env = dict(env)
        self._timeout = timeout

    async def notify(self, argv: Sequence[str]) -> None:
        try:
            rc, _, _ = await self._process.run(
                argv, cwd=self._cwd, env=self._env, timeout=self._timeout)
        except TimeoutError:
            raise RuntimeError("notification command timed out") from None
        except (OSError, ValueError):
            raise RuntimeError("notification command could not be launched") from None
        if rc != 0:
            # Captured command output may contain secrets; only report the exit.
            raise RuntimeError(f"notification command exited {rc}")


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
                  on_stdout_line: Callable[[str], None] | None = None,
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
        tasks: tuple[asyncio.Task, ...] = ()
        try:
            async with asyncio.timeout(timeout):
                if capture:
                    tasks = (
                        asyncio.create_task(_read_stdout(proc.stdout, on_stdout_line)),
                        asyncio.create_task(proc.stderr.read()),
                        asyncio.create_task(proc.wait()),
                    )
                    out, err, _ = await asyncio.gather(*tasks)
                else:
                    await proc.wait()
                    out, err = b"", b""
        except BaseException:
            # One kill-and-wait path for both the seam's timeout and an outer
            # cancellation unwinding through here, plus capture failures.
            await _kill_and_wait(proc)
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            raise
        return (proc.returncode,
                out.decode(errors="replace") if capture else "",
                err.decode(errors="replace") if capture else "")


async def _read_stdout(reader: asyncio.StreamReader, callback: Callable[[str], None] | None
                       ) -> bytes:
    """Capture stdout while publishing each logical line before process exit."""
    chunks: list[bytes] = []
    pending = bytearray()
    while chunk := await reader.read(65536):
        chunks.append(chunk)
        pending.extend(chunk)
        while (end := pending.find(b"\n")) >= 0:
            line = bytes(pending[:end])
            del pending[:end + 1]
            if callback is not None:
                callback(line.removesuffix(b"\r").decode(errors="replace"))
    if pending and callback is not None:
        callback(bytes(pending).decode(errors="replace"))
    return b"".join(chunks)


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

    def publish(self, path: Path, data: bytes) -> None:
        """Link a synced temporary file into place, then sync the directory."""
        path = Path(path)
        directory = path.parent
        existed = directory.exists()
        directory.mkdir(parents=True, exist_ok=True)
        if not existed:
            _fsync_directory(directory.parent)
        tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        linked = False
        tmp_exists = False
        try:
            with tmp.open("xb") as fh:
                tmp_exists = True
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            os.link(tmp, path)
            linked = True
            _fsync_directory(directory)
            os.unlink(tmp)
            tmp_exists = False
            _fsync_directory(directory)
        except BaseException:
            if linked:
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass
            if tmp_exists:
                try:
                    os.unlink(tmp)
                except FileNotFoundError:
                    pass
            try:
                _fsync_directory(directory)
            except OSError:
                pass
            raise

    def read(self, path: Path) -> bytes:
        return Path(path).read_bytes()

    def list(self, directory: Path, pattern: str) -> tuple[Path, ...]:
        directory = Path(directory)
        if not directory.is_dir():
            return ()
        return tuple(sorted(directory.glob(pattern)))

    def remove(self, path: Path) -> None:
        path = Path(path)
        os.unlink(path)
        _fsync_directory(path.parent)


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
