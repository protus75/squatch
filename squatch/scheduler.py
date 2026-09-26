"""The single-flight ticket scheduler."""

import asyncio
from collections.abc import Awaitable, Callable, Iterable


Dispatch = Callable[[str], Awaitable[None]]


class Scheduler:
    """Dispatch the first waiting stem, one at a time.

    An offer is an ordered snapshot rather than an incremental queue update:
    it supersedes the waiting order but cannot interrupt or re-offer the stem
    whose dispatch has already begun.
    """

    def __init__(self, dispatch: Dispatch):
        self._dispatch = dispatch
        self._waiting: tuple[str, ...] = ()
        self._in_flight: str | None = None
        self._worker: asyncio.Task[None] | None = None

    def offer(self, stems: Iterable[str]) -> None:
        """Replace waiting work with an ordered priority snapshot."""
        seen: set[str] = set()
        waiting: list[str] = []
        for stem in stems:
            if stem == self._in_flight or stem in seen:
                continue
            seen.add(stem)
            waiting.append(stem)
        self._waiting = tuple(waiting)
        if self._waiting and (self._worker is None or self._worker.done()):
            self._worker = asyncio.create_task(self._run())

    async def join(self) -> None:
        """Wait until the latest offered work reaches quiescence."""
        while self._worker is not None:
            worker = self._worker
            await worker
            if self._worker is worker:
                return

    async def _run(self) -> None:
        while self._waiting:
            stem, *rest = self._waiting
            self._waiting = tuple(rest)
            self._in_flight = stem
            try:
                await self._dispatch(stem)
            finally:
                self._in_flight = None
