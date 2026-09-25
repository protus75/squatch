"""Injectable seams (SQUATCH_PLAN.md section 15).

Engine code never calls the clock, spawns a process, or writes a file raw; it
goes through one of these so a test can drive a fake. Each seam is the
minimal shape its consumers need and grows only with a consumer.
"""

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
                  ) -> tuple[int, str, str]:
        """Spawn argv (never a shell) and return (rc, out, err)."""
        ...


class Filesystem(Protocol):
    def write(self, path: Path, data: bytes) -> None:
        """Atomic write: temp file, fsync, rename."""
        ...

    def replace(self, src: Path, dst: Path) -> None:
        """Atomic rename of src over dst."""
        ...
