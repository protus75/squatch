"""Restart lifecycle over the Runner's existing lock-held reconciliation path."""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from squatch.journal import Journal
from squatch.runner import Session
from squatch.timers import Timers


@asynccontextmanager
async def restart_session(session: AbstractAsyncContextManager[Session], *,
                          timers: Callable[[Journal], Timers]) -> AsyncIterator[Session]:
    # Entering Runner.session owns lock -> journal -> reconcile -> intake.
    # Calling reconcile here as well would reap twice in the same lifecycle.
    async with session as recovered:
        deadlines = timers(recovered.journal)
        try:
            yield recovered
        finally:
            # The delegated session still holds the lock and open journal.
            await deadlines.shutdown()
