"""Single-flight dispatch admission and its production composition."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Generic, TypeVar, cast

from squatch.config import Config, snapshot
from squatch.scheduler import Scheduler
from squatch.watcher import Watcher


Result = TypeVar("Result")
Work = Callable[[str, Config], Awaitable[Result]]
ConfigSupplier = Callable[[], Config]


class AdmissionTask(Generic[Result]):
    """The observer's handle for an admitted work task."""

    def __init__(self, admission: "DispatchAdmission", task: asyncio.Task[Result]) -> None:
        self._admission = admission
        self._task = task

    def __await__(self):
        return self._observe().__await__()

    async def _observe(self) -> Result:
        try:
            return await self._task
        finally:
            self._admission._release(cast(asyncio.Task[object], self._task))

    def cancel(self) -> bool:
        """Request cancellation of the admitted work."""
        return self._task.cancel()

    def add_done_callback(self, callback: Callable[[asyncio.Task[Result]], object]) -> None:
        """Observe completion without relinquishing admission ownership."""
        self._task.add_done_callback(callback)


class DispatchAdmission:
    """Admit one work task and retain its slot until its outcome is observed."""

    def __init__(self, config_supplier: ConfigSupplier) -> None:
        self._active: asyncio.Task[object] | None = None
        self._config_supplier = config_supplier

    def admit(self, stem: str, work: Work[Result]) -> AdmissionTask[Result] | None:
        """Reserve the slot and return an observation handle, or refuse the offer."""
        if self._active is not None:
            return None

        config = snapshot(self._config_supplier())
        task = asyncio.create_task(work(stem, config))
        self._active = cast(asyncio.Task[object], task)
        return AdmissionTask(self, task)

    def _release(self, task: asyncio.Task[object]) -> None:
        if self._active is task:
            self._active = None


@dataclass(frozen=True)
class DaemonDispatch:
    """The in-process dispatch graph, exposed for its observation boundary."""

    admission: DispatchAdmission
    scheduler: Scheduler
    watcher: Watcher


def compose_daemon_dispatch(config_supplier: ConfigSupplier,
                            work: Work[Result]) -> DaemonDispatch:
    """Compose admission, scheduling, and ticket observation without starting a loop."""
    admission = DispatchAdmission(config_supplier)

    async def dispatch(stem: str) -> None:
        admitted = admission.admit(stem, work)
        if admitted is None:
            raise RuntimeError("scheduler dispatched while admission was occupied")
        await admitted

    scheduler = Scheduler(dispatch)
    return DaemonDispatch(admission, scheduler, Watcher(scheduler))
