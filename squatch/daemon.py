"""Single-flight dispatch admission and its production composition."""

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, TypeVar, cast

from squatch.config import Config, Tier, snapshot
from squatch.control import ControlInbox, Mutation
from squatch.driver import Driver
from squatch.journal import Journal
from squatch.llm import Effort
from squatch.merge import Pipeline
from squatch.rework import Rework
from squatch.scheduler import Scheduler
from squatch.seams import Filesystem
from squatch.specs import Spec
from squatch.triage import Triage
from squatch.watcher import Watcher


Result = TypeVar("Result")
Work = Callable[[str, Config], Awaitable[Result]]
ConfigSupplier = Callable[[], Config]
ConsumerCallback = Callable[[], Awaitable[None]]
PrioritySnapshot = Callable[[], Awaitable[Iterable[str]]]
ShaSupplier = Callable[[], Awaitable[str]]


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


def compose_daemon_rework(*, repo: Path, pipeline: Pipeline, driver: Driver,
                          journal: Journal, fs: Filesystem, spec: Spec,
                          tier: Tier = "medium", effort: Effort = "medium") -> Rework:
    """Compose the dormant post-admission consumer without starting it."""
    return Rework(repo=repo, queue=pipeline.merge_queue, journal=journal, fs=fs,
                  driver=driver, spec=spec, tier=tier, effort=effort)


def compose_daemon_control(*, state_dir: Path, journal: Journal,
                           fs: Filesystem) -> ControlInbox:
    """Compose control intake with the daemon's already lock-held Journal."""
    return ControlInbox(state_dir, journal=journal, fs=fs)


def watcher_consumer(watcher: Watcher, priority_snapshot: PrioritySnapshot) -> ConsumerCallback:
    """Build one deferred priority observation pass."""
    async def consume() -> None:
        watcher.observed(await priority_snapshot())

    return consume


def rework_consumer(rework: Rework, sha: ShaSupplier) -> ConsumerCallback:
    """Build one deferred post-admission Rework pass."""
    async def consume() -> None:
        await rework.run(sha=await sha())

    return consume


def box_consumer(triage: Triage, spec: Spec) -> ConsumerCallback:
    """Build one deferred Suggestion Box triage pass."""
    async def consume() -> None:
        await triage.run(spec)

    return consume


def control_consumer(inbox: ControlInbox, mutate: Mutation) -> ConsumerCallback:
    """Build one deferred pass through the lock holder's control inbox."""
    async def consume() -> None:
        await inbox.consume(mutate)

    return consume


class DaemonTasks:
    """Own the daemon's repeating background consumer tasks."""

    def __init__(self, *, watcher: ConsumerCallback, merge: ConsumerCallback,
                 box: ConsumerCallback, control: ConsumerCallback) -> None:
        self._callbacks = (watcher, merge, box, control)
        self._tasks: tuple[asyncio.Task[None], ...] = ()

    def start(self) -> None:
        """Start each consumer once; callbacks first run in their own tasks."""
        if self._tasks:
            raise RuntimeError("daemon background consumers are already running")
        self._tasks = tuple(asyncio.create_task(self._repeat(callback))
                            for callback in self._callbacks)

    async def shutdown(self) -> None:
        """Cancel, observe, and propagate every consumer's terminal outcome."""
        tasks, self._tasks = self._tasks, ()
        for task in tasks:
            task.cancel()
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        failure = next((outcome for outcome in outcomes
                        if isinstance(outcome, BaseException)
                        and not isinstance(outcome, asyncio.CancelledError)), None)
        if failure is not None:
            raise failure

    async def run(self) -> None:
        """Run until cancelled or a consumer fails, then clean up every sibling."""
        self.start()
        try:
            await asyncio.gather(*self._tasks)
        except BaseException:
            await self.shutdown()
            raise

    @staticmethod
    async def _repeat(callback: ConsumerCallback) -> None:
        while True:
            await callback()
            await asyncio.sleep(0)
