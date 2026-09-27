"""Production ownership of the continuous daemon composition."""

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

import squatch
from squatch.checkpoint import Checkpoint
from squatch.config import Config
from squatch.control import ControlInbox
from squatch.daemon import (ConsumerCallback, DaemonDispatch, DaemonTasks, DispatchPause,
                            PrioritySnapshot, box_consumer, compose_daemon_checkpoint,
                            compose_daemon_dispatch, compose_daemon_heartbeat,
                            compose_daemon_rework, kill_worker_stop_consumer,
                            rework_consumer, watcher_consumer)
from squatch.drain import Drain, fold
from squatch.driver import Driver, Spool
from squatch.effects import Effects
from squatch.enginelog import EngineLog
from squatch.git import Git
from squatch.heartbeat import Heartbeat
from squatch.journal import Journal
from squatch.llmeffect import LLMEffect
from squatch.merge import Pipeline
from squatch.providers import CliClient, Registry
from squatch.redact import Redactor
from squatch.rework import Rework
from squatch.runner import EXIT_OK, Dispatched, PipelineFactory, Refusal, Runner, Session
from squatch.seams import Clock, Filesystem, ProcessExec, Sleep
from squatch.specs import load_spec
from squatch.tickets import Intake, Ticket
from squatch.triage import Triage


SPECS = Path(squatch.__file__).resolve().parent.parent / "specs"
POLL_SECONDS = 1.0
CONTROL_POLL_SECONDS = .05
ControlFactory = Callable[[Journal], tuple[DispatchPause, ConsumerCallback]]


class _WorkerOwnedPause:
    """Observe pause state while the control worker remains the sole inbox consumer."""

    def __init__(self, pause: DispatchPause) -> None:
        self._pause = pause
        self.inbox = pause.inbox

    async def allow_offer(self, stem: str | None = None) -> bool:
        return (self._pause.hold_id is None
                and (stem is None or not self._pause.holds_offer(stem)))

    def holds_offer(self, stem: str) -> bool:
        return self._pause.holds_offer(stem)


@dataclass
class ServeGraph:
    """The live object graph, exposed so the bounded soak can drive its seams."""

    dispatch: DaemonDispatch
    pipeline: Pipeline
    rework: Rework
    triage: Triage
    control: ControlInbox
    checkpoint: Checkpoint
    heartbeat: Heartbeat
    tasks: DaemonTasks
    stopped: asyncio.Event

    async def run(self) -> int:
        """Run until an applied kill, an outer signal, or a worker failure."""
        owner = asyncio.create_task(self.tasks.run())
        killed = asyncio.create_task(self.stopped.wait())
        try:
            done, _ = await asyncio.wait((owner, killed), return_when=asyncio.FIRST_COMPLETED)
            if owner in done:
                killed.cancel()
                await asyncio.gather(killed, return_exceptions=True)
                await owner
                raise RuntimeError("daemon workers stopped without a kill")
            owner.cancel()
            outcome, = await asyncio.gather(owner, return_exceptions=True)
            if (isinstance(outcome, BaseException)
                    and not isinstance(outcome, asyncio.CancelledError)):
                raise outcome
            return EXIT_OK
        except BaseException:
            owner.cancel()
            killed.cancel()
            await asyncio.gather(owner, killed, return_exceptions=True)
            raise


def compose_serve_graph(*, repo: Path, state_dir: Path, journal: Journal,
                        config_supplier: Callable[[], Config], pipeline: Pipeline,
                        pause: DispatchPause, rework: Rework, triage: Triage, git: Git,
                        fs: Filesystem, clock: Clock, work: Callable[[str, Config],
                        Awaitable[Dispatched]], priority_snapshot: PrioritySnapshot,
                        sha: Callable[[], Awaitable[str]],
                        sleep: Sleep = asyncio.sleep) -> ServeGraph:
    """Compose every daemon boundary without starting a task or host run."""
    stopped = asyncio.Event()
    checkpoint = compose_daemon_checkpoint(repo=repo, git=git, journal=journal)

    async def dispatch_work(stem: str, config: Config) -> None:
        result = await work(stem, config)
        if result.settled:
            await checkpoint.push(stem, result.run_seq)

    async def wait_for_control() -> None:
        await sleep(CONTROL_POLL_SECONDS)

    dispatch = compose_daemon_dispatch(
        config_supplier, dispatch_work, pause=_WorkerOwnedPause(pause),
        wait_for_control=wait_for_control)

    tasks: DaemonTasks
    heartbeat = None
    triage_spec = load_spec(SPECS / "triage.md")

    async def watch() -> None:
        await watcher_consumer(dispatch.watcher, priority_snapshot)()
        assert heartbeat is not None
        heartbeat.beat()
        await sleep(POLL_SECONDS)

    async def box() -> None:
        if triage._box.pending():
            await box_consumer(triage, triage_spec)()
        await sleep(POLL_SECONDS)

    async def control() -> None:
        await kill_worker_stop_consumer(
            pause.inbox, pipeline.stages, tasks, mutate=pause.apply, stopped=stopped)()
        if not stopped.is_set():
            await sleep(CONTROL_POLL_SECONDS)

    tasks = DaemonTasks(
        watcher=watch,
        merge=rework_consumer(rework, sha),
        box=box,
        control=control)
    heartbeat = compose_daemon_heartbeat(
        state_dir=state_dir, tasks=tasks, clock=clock, fs=fs)
    return ServeGraph(
        dispatch=dispatch, pipeline=pipeline, rework=rework, triage=triage,
        control=pause.inbox, checkpoint=checkpoint, heartbeat=heartbeat,
        tasks=tasks, stopped=stopped)


class Serve:
    """Hold one reconciled writer session around the production daemon graph."""

    def __init__(self, *, runner: Runner, repo: Path, config_supplier: Callable[[], Config],
                 pipeline: PipelineFactory, control: ControlFactory, git: Git,
                 fs: Filesystem, clock: Clock, process: ProcessExec,
                 env: Mapping[str, str], report: Callable[[str], None],
                 sleep: Sleep = asyncio.sleep) -> None:
        self._runner = runner
        self._repo = Path(repo)
        self._config_supplier = config_supplier
        self._pipeline = pipeline
        self._control = control
        self._git = git
        self._fs = fs
        self._clock = clock
        self._process = process
        self._env = env
        self._report = report
        self._sleep = sleep
        self.graph: ServeGraph | None = None

    async def run(self) -> int:
        try:
            async with self._runner.session() as session:
                self.graph = self.compose(session)
                return await self.graph.run()
        except Refusal:
            raise
        except Exception as error:
            raise Refusal(f"serve worker failed: {type(error).__name__}: {error}",
                          f"inspect {self._runner.log_path}, fix the worker, then restart "
                          "`squatch serve`") from None

    def compose(self, session: Session) -> ServeGraph:
        """Build the real graph under an already reconciled, lock-held session."""
        journal = session.journal
        config = self._config_supplier()
        state_dir = self._repo / config.state_dir
        pause, _ = self._control(journal)
        pipeline = self._pipeline(journal)
        if pipeline.merge_queue is None:
            raise ValueError("production serve requires the merge queue")

        redact = Redactor.from_config(config, self._env)
        registry = Registry(config)
        client = CliClient(
            registry, process=self._process, fs=self._fs, env=self._env, redact=redact,
            state_dir=state_dir, cwd=self._repo)
        llm = LLMEffect(
            llm=client, effects=Effects(journal), redact=redact, clock=self._clock)
        driver = Driver(
            llm=llm, spool=Spool(state_dir, fs=self._fs, redact=redact),
            log=EngineLog(state_dir, clock=self._clock, redact=redact), clock=self._clock,
            retry_cap=config.caps.retry, severity=config.review.gate_severity)
        rework = compose_daemon_rework(
            repo=self._repo, pipeline=pipeline, driver=driver, journal=journal, fs=self._fs,
            spec=load_spec(SPECS / "rework.md"), tier=config.routing_default_tier)
        triage = Triage(
            repo=self._repo, config=config, git=self._git, fs=self._fs, clock=self._clock,
            journal=journal,
            llm=CliClient(
                registry, process=self._process, fs=self._fs, env=self._env, redact=redact,
                state_dir=state_dir, cwd=self._repo),
            log=EngineLog(state_dir, clock=self._clock, redact=redact), redact=redact,
            report=self._report)

        tickets: dict[str, Ticket] = {}

        async def priority_snapshot() -> tuple[str, ...]:
            intake = Intake(repo=self._repo, git=self._git, journal=journal, fs=self._fs)
            self._runner._report_intake(await intake.run())
            current = self._config_supplier()
            scanner = Drain(
                runner=self._runner, repo=self._repo, config=current, git=self._git,
                clock=self._clock, process=self._process, env=self._env, report=self._report)
            facts = fold(journal.read())
            plane = await scanner._scan(facts)
            scanner._refuse_cycles(plane)
            ready = scanner._eligible(plane, facts)
            tickets.clear()
            tickets.update((ticket.stem, ticket) for ticket in ready)
            return tuple(ticket.stem for ticket in ready
                         if not pause.holds_offer(ticket.stem))

        async def work(stem: str, _captured: Config) -> Dispatched:
            ticket = tickets.get(stem)
            if ticket is None:
                raise RuntimeError(f"watcher dispatched stale ticket {stem}")
            self._runner._eligible(ticket, journal)
            return await self._runner.dispatch(ticket, journal)

        async def sha() -> str:
            return await self._git.rev_parse(self._repo, "HEAD")

        return compose_serve_graph(
            repo=self._repo, state_dir=state_dir, journal=journal,
            config_supplier=self._config_supplier, pipeline=pipeline, pause=pause,
            rework=rework, triage=triage, git=self._git, fs=self._fs, clock=self._clock,
            work=work, priority_snapshot=priority_snapshot, sha=sha, sleep=self._sleep)
