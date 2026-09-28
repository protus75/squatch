"""Single-flight dispatch admission and its production composition."""

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from contextlib import AbstractAsyncContextManager, contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Generic, TypeVar, cast
from uuid import UUID, uuid4

from squatch.config import Config, Tier, snapshot
from squatch.box import Box, STORM_BREAKER_ORIGIN, scoped_occurrence_recorder
from squatch.checkpoint import Checkpoint
from squatch.control import ControlInbox, ControlRequest, Mutation
from squatch.driver import Driver
from squatch.flake import Flake
from squatch.git import Git
from squatch.heartbeat import Heartbeat
from squatch.journal import Journal
from squatch.llm import Effort
from squatch.lockfile import Holder
from squatch.merge import Pipeline
from squatch.providers import ProviderRuntime, Registry
from squatch.rework import Rework
from squatch.restart import restart_session
from squatch.runner import RecoveredSession, Session
from squatch.scheduler import Scheduler
from squatch.seams import Clock, Filesystem, Sleep
from squatch.specs import Spec
from squatch.storm import StormLedger
from squatch.triage import Triage
from squatch.timers import Timers
from squatch.watcher import Watcher


Result = TypeVar("Result")
Work = Callable[[str, Config], Awaitable[Result]]
ConfigSupplier = Callable[[], Config]
ConsumerCallback = Callable[[], Awaitable[None]]
PrioritySnapshot = Callable[[], Awaitable[Iterable[str]]]
ShaSupplier = Callable[[], Awaitable[str]]


class DispatchPause:
    """Consume identity-bound control decisions at the next dispatch boundary."""

    def __init__(self, inbox: ControlInbox) -> None:
        self.inbox = inbox
        self.hold_id: UUID | None = next(iter(inbox.holds), None)
        self._applied: set[UUID] = set()

    async def allow_offer(self, stem: str | None = None) -> bool:
        await self.inbox.consume(self.apply)
        return self.hold_id is None

    def holds_offer(self, stem: str) -> bool:
        """Whether an independently owned hold suppresses this exact offer."""
        return False

    async def apply(self, request: ControlRequest) -> None:
        if request.request_id in self._applied:
            return
        if request.action == "pause":
            if self.hold_id is not None:
                self.inbox.discard_hold(self.hold_id)
            # A pause request's immutable identity is also its release handle,
            # so a publisher can tell the operator how to resume it.
            self.hold_id = self.inbox.hold(request.request_id)
        elif request.action == "release" and request.hold_id == self.hold_id:
            self.hold_id = None
        self._applied.add(request.request_id)


class DrainControl(DispatchPause):
    """Coordinate bootstrap-drain control with its in-flight dispatch."""

    def __init__(self, inbox: ControlInbox) -> None:
        super().__init__(inbox)
        self.stopping = False
        self._abort: ConsumerCallback | None = None
        self._dispatch_control: ConsumerCallback | None = None
        self._dispatch: asyncio.Task[object] | None = None

    def bind_abort(self, abort: ConsumerCallback) -> None:
        """Bind the Stages-owned Driver abort after pipeline composition."""
        self._abort = abort

    def bind_dispatch_control(self, consume: ConsumerCallback) -> None:
        """Bind the kill-filtered control poll used during dispatch."""
        self._dispatch_control = consume

    async def apply(self, request: ControlRequest) -> None:
        await super().apply(request)
        if request.action != "kill":
            return
        self.stopping = True
        if self._abort is not None:
            await self._abort()
        active = self._dispatch
        if active is not None and not active.done():
            active.cancel()
            await asyncio.gather(active, return_exceptions=True)

    async def run_dispatch(self, dispatch: Awaitable[Result], wait_for_control: ConsumerCallback
                           ) -> Result | None:
        """Consume kill concurrently while owning the dispatch through unwind."""
        if self.stopping:
            return None
        active = asyncio.create_task(dispatch)
        self._dispatch = cast(asyncio.Task[object], active)

        async def consume_until_stopping() -> None:
            consume = self._dispatch_control or wait_for_control
            while not self.stopping:
                await consume()

        control = asyncio.create_task(consume_until_stopping())
        try:
            await asyncio.wait((active, control), return_when=asyncio.FIRST_COMPLETED)
            if control.done() and not self.stopping:
                try:
                    await control
                except BaseException:
                    active.cancel()
                    await asyncio.gather(active, return_exceptions=True)
                    raise
            if self.stopping:
                await control
                await asyncio.gather(active, return_exceptions=True)
                return None
            control.cancel()
            await asyncio.gather(control, return_exceptions=True)
            return await active
        finally:
            if not active.done():
                active.cancel()
            if not control.done():
                control.cancel()
            await asyncio.gather(active, control, return_exceptions=True)
            self._dispatch = None


class StormDispatchHold:
    """Materialize and release trip-bound holds for exact ticket origins."""

    def __init__(self, inbox: ControlInbox, journal: Journal) -> None:
        self.inbox = inbox
        self._journal = journal
        self._active: dict[UUID, tuple[str, str]] = {}
        self._materialized: set[str] = set()
        self._restore()

    def _restore(self) -> None:
        self._active.clear()
        self._materialized.clear()
        for event in self._journal.read():
            body = event.body
            if (event.type != "signal" or body.get("kind") != "control_hold"
                    or body.get("trigger") != "storm_trip"):
                continue
            try:
                hold_id = UUID(body["hold_id"])
                trip_id, stem = body["trip_id"], body["stem"]
            except (KeyError, TypeError, ValueError):
                continue
            self._materialized.add(trip_id)
            if hold_id in self.inbox.holds:
                self._active[hold_id] = (trip_id, stem)

    def holds_offer(self, stem: str) -> bool:
        """Journal each matching trip decision before suppressing its offer."""
        for trip in StormLedger(journal=self._journal).trips():
            if trip["trip_id"] in self._materialized or trip["emitting_origin"] != stem:
                continue
            hold_id = uuid4()
            self._journal.append("signal", {
                "kind": "control_hold", "hold_id": str(hold_id), "released": False,
                "lifecycle": str(self.inbox.lifecycle), "trigger": "storm_trip",
                "trip_id": trip["trip_id"], "stem": stem,
            }, ticket=stem)
            # The event is the decision; only after it commits does in-memory
            # dispatch state change. Rehydration repairs a crash at this seam.
            self.inbox.rehydrate_holds()
            self._restore()
        return any(active_stem == stem for _, active_stem in self._active.values())

    async def apply(self, request: ControlRequest) -> None:
        if request.action == "release" and request.hold_id in self._active:
            self._active.pop(request.hold_id)


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
    pause: DispatchPause | None = None


def compose_daemon_dispatch(config_supplier: ConfigSupplier,
                            work: Work[Result], *, pause: DispatchPause | None = None,
                            wait_for_control: ConsumerCallback | None = None) -> DaemonDispatch:
    """Compose admission, scheduling, and ticket observation without starting a loop."""
    if pause is not None and wait_for_control is None:
        raise ValueError("pause requires wait_for_control")
    admission = DispatchAdmission(config_supplier)

    async def dispatch(stem: str) -> None:
        if pause is not None:
            while not await pause.allow_offer(stem):
                assert wait_for_control is not None
                await wait_for_control()
        admitted = admission.admit(stem, work)
        if admitted is None:
            raise RuntimeError("scheduler dispatched while admission was occupied")
        await admitted

    scheduler = Scheduler(dispatch)
    return DaemonDispatch(admission, scheduler, Watcher(scheduler), pause)


def compose_daemon_rework(*, repo: Path, pipeline: Pipeline, driver: Driver,
                          journal: Journal, fs: Filesystem, spec: Spec,
                          tier: Tier = "medium", effort: Effort = "medium") -> Rework:
    """Compose the dormant post-admission consumer without starting it."""
    return Rework(repo=repo, queue=pipeline.merge_queue, journal=journal, fs=fs,
                  driver=driver, spec=spec, tier=tier, effort=effort)


def compose_daemon_flake(*, journal: Journal, box: Box) -> Flake:
    """Compose the dormant, report-keyed flake quarantine boundary."""
    return Flake(journal=journal, box=box)


def compose_daemon_checkpoint(*, repo: Path, git: Git, journal: Journal) -> Checkpoint:
    """Compose the dormant checkpoint publication boundary."""
    return Checkpoint(repo=repo, git=git, journal=journal)


@contextmanager
def compose_daemon_storm_producer(*, state_dir: Path, journal: Journal,
                                  fs: Filesystem, clock: Clock):
    """Temporarily bind the lock holder's occurrence producer to its Box."""
    ledger = StormLedger(journal=journal)

    box = Box(state_dir, fs=fs, clock=clock)

    def repair() -> None:
        for crossing in ledger.crossings():
            ledger.trip(crossing)
            origin = f"{STORM_BREAKER_ORIGIN}P0:{crossing['trip_id']}"
            if box.by_origin(origin) is not None:
                continue
            identities = (f"{crossing['signature']}: "
                          f"{crossing['first_live_occurrence_id']} -> "
                          f"{crossing['crossing_occurrence_id']}")
            box.enqueue(
                message_class="failure_report", origin=origin,
                summary=f"P0 storm trip {crossing['trip_id']}",
                detail=f"P0 storm trip {crossing['trip_id']}: {identities}",
                stage=crossing["emitting_stage"])

    def record(**values) -> bool:
        if "emitting_origin" not in values:
            message_id = values["occurrence_id"].rsplit("/", 1)[0]
            values["emitting_origin"] = box.get(message_id).origin
        wrote = ledger.record(**values)
        if wrote:
            repair()
        return wrote

    with scoped_occurrence_recorder(state_dir=state_dir, recorder=record):
        for _, message in box._records():
            if message.origin.startswith(STORM_BREAKER_ORIGIN):
                continue
            for report in range(1, message.reports + 1):
                record(signature=message.signature,
                       occurrence_id=f"{message.id}/{report}",
                       emitting_stage=message.stage,
                       emitting_origin=message.origin)
        repair()
        yield


def compose_daemon_control(*, state_dir: Path, journal: Journal,
                           fs: Filesystem, holder: Holder | None = None) -> ControlInbox:
    """Compose control intake with the daemon's already lock-held Journal."""
    lifecycle = ControlInbox.active_lifecycle(journal)
    inbox = ControlInbox(state_dir, journal=journal, fs=fs, lifecycle=lifecycle)
    inbox.rehydrate_holds()
    lifecycle = {"kind": "control_lifecycle", "lifecycle": str(inbox.lifecycle)}
    if holder is not None:
        lifecycle["holder"] = asdict(holder)
    journal.append("signal", lifecycle)
    return inbox


def compose_daemon_heartbeat(*, state_dir: Path, tasks: "DaemonTasks",
                             clock: Clock, fs: Filesystem) -> Heartbeat:
    """Compose the dormant core-worker liveness boundary without scheduling it."""
    return Heartbeat(state_dir=state_dir, tasks=tasks, clock=clock, fs=fs)


def compose_daemon_timers(*, journal: Journal, clock: Clock,
                          sleep: Sleep = asyncio.sleep) -> Timers:
    """Re-arm the lock holder's deadlines from its journal exactly once."""
    timers = Timers(journal=journal, clock=clock, sleep=sleep)
    timers.rearm()
    return timers


def compose_daemon_restart(*, session: AbstractAsyncContextManager[RecoveredSession],
                           registry: Registry, clock: Clock) -> AbstractAsyncContextManager[Session]:
    """Delegate recovery to Runner.session and bind timers to that lifetime."""
    return restart_session(
        session,
        timers=lambda journal: compose_daemon_timers(journal=journal, clock=clock),
        providers=lambda timers: ProviderRuntime(registry, timers=timers, clock=clock))


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


def driver_abort_consumer(inbox: ControlInbox, driver: Driver) -> ConsumerCallback:
    """Build the dormant kill mutation for the active Driver invocation."""
    async def abort(request: ControlRequest) -> None:
        if request.action == "kill":
            await driver.abort_active()

    return control_consumer(inbox, abort)


class DaemonTasks:
    """Own the daemon's repeating background consumer tasks."""

    def __init__(self, *, watcher: ConsumerCallback, merge: ConsumerCallback,
                 box: ConsumerCallback, control: ConsumerCallback) -> None:
        self._callbacks = (watcher, merge, box, control)
        self._tasks: tuple[asyncio.Task[None], ...] = ()
        self._workers: tuple[asyncio.Task[None], ...] = ()
        self._control: asyncio.Task[None] | None = None
        self._workers_stopped = False
        self._kill_stopping = False

    def start(self) -> None:
        """Start each consumer once; callbacks first run in their own tasks."""
        if self._tasks:
            raise RuntimeError("daemon background consumers are already running")
        self._tasks = tuple(asyncio.create_task(self._repeat(callback))
                            for callback in self._callbacks)
        self._workers, self._control = self._tasks[:3], self._tasks[3]
        self._workers_stopped = False
        self._kill_stopping = False

    @property
    def workers_live(self) -> bool:
        """Whether every watched worker is still running in this lifecycle."""
        return (not self._workers_stopped and len(self._workers) == 3
                and all(not task.done() and not task.cancelling() for task in self._workers))

    async def stop_workers(self) -> None:
        """Stop the worker siblings without interrupting their control caller."""
        if self._workers_stopped:
            return
        self._workers_stopped = True
        for task in self._workers:
            task.cancel()
        outcomes = await asyncio.gather(*self._workers, return_exceptions=True)
        failure = next((outcome for outcome in outcomes
                        if isinstance(outcome, BaseException)
                        and not isinstance(outcome, asyncio.CancelledError)), None)
        if failure is not None:
            raise failure

    async def stop_workers_for_kill(self) -> None:
        """Mark and stop workers after the current-lifecycle kill is accepted."""
        self._kill_stopping = True
        await self.stop_workers()

    async def shutdown(self) -> None:
        """Cancel, observe, and propagate every consumer's terminal outcome."""
        tasks, self._tasks = self._tasks, ()
        self._workers, self._control = (), None
        self._workers_stopped = False
        self._kill_stopping = False
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
            try:
                await asyncio.gather(*self._tasks)
            except asyncio.CancelledError:
                if not self._kill_stopping or asyncio.current_task().cancelling():
                    raise
                assert self._control is not None
                await self._control
        except BaseException:
            await self.shutdown()
            raise

    @staticmethod
    async def _repeat(callback: ConsumerCallback) -> None:
        while True:
            await callback()
            await asyncio.sleep(0)


def kill_worker_stop_consumer(inbox: ControlInbox, driver: Driver,
                              tasks: DaemonTasks, *, mutate: Mutation | None = None,
                              stopped: asyncio.Event | None = None) -> ConsumerCallback:
    """Apply control, then unwind active work before stopping worker siblings.

    ``stopped`` is published only after the inbox has journaled the applied
    decision, so the production serve owner can leave its lifetime without
    racing the control record.
    """
    async def stop(request: ControlRequest) -> None:
        if mutate is not None:
            await mutate(request)
        if request.action == "kill":
            await driver.abort_active()
            await tasks.stop_workers_for_kill()

    consume = control_consumer(inbox, stop)

    async def consume_and_publish_stop() -> None:
        await consume()
        if tasks._kill_stopping and stopped is not None:
            stopped.set()

    return consume_and_publish_stop
