"""Dormant liveness heartbeat for the daemon's core workers."""

from datetime import datetime
from pathlib import Path
from typing import Protocol

from squatch.seams import Clock, Filesystem


class WorkerLiveness(Protocol):
    """The daemon task-owner observation surface needed by a heartbeat."""

    @property
    def workers_live(self) -> bool:
        ...


class Heartbeat:
    """Write one state-directory heartbeat only while core workers are live."""

    def __init__(self, *, state_dir: Path, tasks: WorkerLiveness,
                 clock: Clock, fs: Filesystem) -> None:
        self.path = state_dir / "heartbeat"
        self._tasks = tasks
        self._clock = clock
        self._fs = fs

    def beat(self) -> bool:
        """Write one timestamp when the watcher, merge, and box workers are live."""
        if not self._tasks.workers_live:
            return False
        timestamp = self._clock()
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("heartbeat clock must return an aware timestamp")
        self._fs.write(self.path, timestamp.isoformat().encode())
        return True
