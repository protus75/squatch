"""The adapter from ticket-plane observations to scheduler offers."""

from collections.abc import Iterable

from squatch.scheduler import Scheduler


class Watcher:
    """Forward each observed priority snapshot without starting another loop."""

    def __init__(self, scheduler: Scheduler):
        self._scheduler = scheduler

    def observed(self, priority_snapshot: Iterable[str]) -> None:
        """Record one ticket-plane observation as the scheduler's latest offer."""
        self._scheduler.offer(priority_snapshot)
