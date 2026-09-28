"""Journaled deadlines; firing is the durable timer_fired event."""

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from squatch.journal import Event, Journal, JournalCorruption, render_ts
from squatch.seams import Clock, Sleep


@dataclass(frozen=True)
class Deadline:
    at: datetime
    fired: bool = False


def fold_deadlines(events: Iterable[Event]) -> dict[str, Deadline]:
    deadlines: dict[str, Deadline] = {}
    for event in events:
        if event.type not in {"timer_armed", "timer_fired"}:
            continue
        # The bootstrap drain owns its separate runtime-ceiling records.
        if event.body.get("kind") != "deadline":
            continue
        try:
            if not event.key:
                raise ValueError("deadline needs a key")
            at = datetime.fromisoformat(event.body["deadline"])
            render_ts(at)
            previous = deadlines.get(event.key)
            if previous is not None and previous.at != at:
                raise ValueError("deadline key reused with a different time")
            if event.type == "timer_fired" and previous is None:
                raise ValueError("deadline fired without an arm")
            deadlines[event.key] = Deadline(
                at, event.type == "timer_fired" or (previous is not None and previous.fired))
        except (KeyError, TypeError, ValueError) as error:
            raise JournalCorruption(f"invalid deadline {event.key!r}: {error}") from error
    return deadlines


class Timers:
    """One session's tasks over durable, immutable deadline identities."""

    def __init__(self, *, journal: Journal, clock: Clock,
                 sleep: Sleep = asyncio.sleep) -> None:
        self._journal = journal
        self._clock = clock
        self._sleep = sleep
        self._deadlines: dict[str, Deadline] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._rearmed = False
        self._closed = False

    def rearm(self) -> None:
        """Fold once; expired deadlines fire before any session work is offered."""
        self._require_open()
        if self._rearmed:
            return
        self._deadlines = fold_deadlines(self._journal.read())
        pending = [key for key, deadline in self._deadlines.items() if not deadline.fired]
        if pending:
            now = self._clock()
            render_ts(now)
            for key in pending:
                if self._deadlines[key].at <= now:
                    self._fire(key)
            for key in pending:
                if not self._deadlines[key].fired:
                    self._tasks[key] = asyncio.create_task(self._wait(key))
        self._rearmed = True

    def arm(self, key: str, at: datetime) -> None:
        """Persist before scheduling; repeating the same identity is inert."""
        self.rearm()
        if not isinstance(key, str) or not key:
            raise ValueError("deadline needs a nonempty string key")
        timestamp = render_ts(at)
        previous = self._deadlines.get(key)
        if previous is not None:
            if previous.at != at:
                raise ValueError("deadline key reused with a different time")
            return
        now = self._clock()
        render_ts(now)
        self._journal.append("timer_armed", {"kind": "deadline", "deadline": timestamp},
                             key=key)
        self._deadlines[key] = Deadline(at)
        if at <= now:
            self._fire(key)
        else:
            self._tasks[key] = asyncio.create_task(self._wait(key))

    def pending(self, prefix: str) -> datetime | None:
        """The last live deadline under a prefix, firing elapsed windows first."""
        self.rearm()
        now = self._clock()
        render_ts(now)
        pending = []
        for key, deadline in tuple(self._deadlines.items()):
            if deadline.fired:
                continue
            if deadline.at <= now:
                self._fire(key)
            elif key.startswith(prefix):
                pending.append(deadline.at)
        return max(pending, default=None)

    async def _wait(self, key: str) -> None:
        while True:
            now = self._clock()
            render_ts(now)
            remaining = (self._deadlines[key].at - now).total_seconds()
            if remaining <= 0:
                self._fire(key)
                return
            await self._sleep(remaining)

    def _fire(self, key: str) -> None:
        deadline = self._deadlines[key]
        if deadline.fired:
            return
        self._journal.append("timer_fired", {
            "kind": "deadline", "deadline": render_ts(deadline.at)}, key=key)
        self._deadlines[key] = Deadline(deadline.at, fired=True)

    async def shutdown(self) -> None:
        """Observe every task before the owning session closes its journal."""
        self._closed = True
        tasks, self._tasks = tuple(self._tasks.values()), {}
        for task in tasks:
            task.cancel()
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        failure = next((outcome for outcome in outcomes
                        if isinstance(outcome, BaseException)
                        and not isinstance(outcome, asyncio.CancelledError)), None)
        if failure is not None:
            raise failure

    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeError("timers are shut down")
