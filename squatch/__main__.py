"""`python -m squatch <verb>`: the module entry (SQUATCH_PLAN.md section 18).

stdlib argparse, the bootstrap verbs -- `status`, `new <stem>`, `run <stem>`,
`drain [--parked <stem>]...`, `serve`, and `triage` -- plus the section 18 exit-code contract: 0
settled or quiescent, 1 a non-ok ticket terminal or a ceiling-halted drain,
2 an engine-plane refusal. Nothing reaches the operator as a raw traceback:
every refusal prints its message and paved road. The checkout root is the
invocation cwd; `--config` relocates only the config file. `--parked` is the
self-upgrade handoff's continuity flag: the drain's re-exec child carries
the parent's parked set in it (section 18). The project stays virtual: this
module entry is the whole CLI surface until the release path (section 13
touchpoint 6) earns a console script.
"""

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO
from uuid import UUID

import squatch
from squatch.box import BoxCorruption
from squatch.config import ConfigError, load
from squatch.control import ControlRequest, publish_control
from squatch.daemon import (DrainControl, compose_daemon_control, compose_daemon_dispatch,
                            compose_daemon_restart, compose_daemon_storm_producer,
                            StormDispatchHold)
from squatch.drain import Drain
from squatch.enginelog import EngineLog
from squatch.git import Git, GitError
from squatch.journal import Journal, JournalCorruption, read_events
from squatch.lockfile import Holder, LOCK_NAME, LockHeld, Lockfile
from squatch.providers import CliClient, Registry, child_env
from squatch.redact import Redactor
from squatch.merge import compose_pipeline
from squatch.mergequeue import AdmissionHold
from squatch.runner import EXIT_OK, EXIT_REFUSED, PipelineFactory, Refusal, Runner
from squatch.seams import (Clock, ExecutableNotFound, LocalFilesystem, ProcessExec,
                           SubprocessExec)
from squatch.serve import Serve
from squatch.status import project, render
from squatch.specs import load_spec
from squatch.tickets import new_ticket
from squatch.triage import Triage

ENGINE_ROOT = Path(squatch.__file__).resolve().parent.parent
GIT_TIMEOUT_SECONDS = 60.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m squatch", description="squatch scaffold verbs")
    p.add_argument("--config", type=Path, default=None,
                   help="config file (default: config.yaml at the invocation cwd)")
    sub = p.add_subparsers(dest="verb", required=True)
    sub.add_parser("status", help="project current state from the journal (read-only)")
    new = sub.add_parser("new", help="template tickets/<stem>/ticket.md and lint it")
    new.add_argument("stem")
    run = sub.add_parser("run", help="drive one ticket through intake, the lock, and dispatch")
    run.add_argument("stem")
    confirm = sub.add_parser("confirm", help="confirm a draft or re-enqueue a parked ticket")
    confirm.add_argument("stem")
    reject = sub.add_parser("reject", help="reject a ticket and report its dead dependencies")
    reject.add_argument("stem")
    drain = sub.add_parser("drain", help="run every eligible ticket, one at a time, to quiescence")
    drain.add_argument("--parked", action="append", default=[], metavar="STEM",
                       help="a stem the handing-off parent drain had parked (repeatable; "
                            "the self-upgrade re-exec sets it, never an operator)")
    sub.add_parser("serve", help="run the continuous daemon until stopped")
    sub.add_parser("pause", help="pause dispatch at its next safe boundary")
    sub.add_parser("kill", help="stop the live drain or serve process and active work")
    resume = sub.add_parser("resume", help="release one dispatch pause hold")
    resume.add_argument("--hold-id", type=UUID, required=True)
    sub.add_parser("triage", help="triage every pending Suggestion Box message once, then stop")
    return p


def main(argv: Sequence[str] | None = None, *, cwd: Path | None = None,
         env: Mapping[str, str] | None = None, out: TextIO | None = None,
         pipeline: PipelineFactory | None = None, clock: Clock = _now,
         process: ProcessExec | None = None) -> int:
    """`pipeline`, `clock`, and `process` are the test seams: a scripted
    stage-dispatch factory over the lock-held journal, the clock every verb
    reads, and the process-exec seam git, the stages, and the drain's
    self-upgrade handoff spawn through."""
    out = out if out is not None else sys.stdout
    cwd = Path(cwd) if cwd is not None else Path.cwd()
    env = dict(env if env is not None else os.environ)
    process = process if process is not None else SubprocessExec()
    try:
        args = _parser().parse_args(argv)
    except SystemExit as e:  # argparse already printed usage or help
        return int(e.code or 0)
    try:
        return {"status": _status, "new": _new, "run": _run, "confirm": _confirm,
                "reject": _reject, "drain": _drain, "serve": _serve, "triage": _triage,
                "pause": _control, "resume": _control, "kill": _control}[args.verb](
            args, cwd, env, out, pipeline, clock, process)
    except Refusal as e:
        print(f"refused: {e.message}", file=out)
        print(f"  paved road: {e.paved_road}", file=out)
        return EXIT_REFUSED


def _status(args, cwd: Path, env, out: TextIO, pipeline, clock, process) -> int:
    config = _config(args, cwd)
    state_dir = cwd / config.state_dir
    try:
        status = project(read_events(state_dir), repo=cwd, state_dir=state_dir)
    except JournalCorruption as e:
        raise Refusal(f"journal corruption: {e}",
                      "a corrupt record is never skipped; inspect the named segment line") from None
    except BoxCorruption as e:
        raise Refusal(f"box corruption: {e}",
                      "repair or remove the named corrupt box message, then re-run `status`") from None
    out.write(render(status))
    return 0


def _new(args, cwd: Path, env, out: TextIO, pipeline, clock, process) -> int:
    try:
        path, findings = new_ticket(cwd, args.stem, fs=LocalFilesystem())
    except (ValueError, FileExistsError) as e:
        raise Refusal(str(e), "pick a fresh kebab-case stem, then edit the templated file") from None
    print(f"authored {path.relative_to(cwd)}", file=out)
    if findings:
        print("lint findings to resolve before intake:", file=out)
        for f in findings:
            print(f"  {f.message} -- {f.paved_road}", file=out)
    else:
        print("lint: clean; the next `run`/`drain` intakes it", file=out)
    return 0


def _run(args, cwd: Path, env, out: TextIO, pipeline, clock, process) -> int:
    return _locked(args, cwd, env, out, pipeline, clock, process,
                   lambda runner, config, git, control: runner.run(args.stem))


def _confirm(args, cwd: Path, env, out: TextIO, pipeline, clock, process) -> int:
    return _locked(args, cwd, env, out, pipeline, clock, process,
                   lambda runner, config, git, control: runner.confirm(args.stem))


def _reject(args, cwd: Path, env, out: TextIO, pipeline, clock, process) -> int:
    return _locked(args, cwd, env, out, pipeline, clock, process,
                   lambda runner, config, git, control: runner.reject(args.stem))


def _drain(args, cwd: Path, env, out: TextIO, pipeline, clock, process) -> int:
    return _locked(args, cwd, env, out, pipeline, clock, process,
                   lambda runner, config, git, control: Drain(
                       runner=runner, repo=cwd, config=config, git=git, clock=clock,
                       process=process, env=env, config_path=args.config,
                       carried=args.parked,
                       control_factory=control,
                       report=lambda line: print(line, file=out)).run())


def _serve(args, cwd: Path, env, out: TextIO, pipeline, clock, process) -> int:
    def run(runner, config, git, control):
        return Serve(
            runner=runner, repo=cwd, config_supplier=lambda: _config(args, cwd),
            pipeline=runner._pipeline, control=control, git=git, fs=LocalFilesystem(),
            clock=clock, process=process, env=env,
            report=lambda line: print(line, file=out)).run()

    return _locked(args, cwd, env, out, pipeline, clock, process, run)


class _AdmissionDispatchPause(DrainControl):
    def __init__(self, inbox, journal):
        super().__init__(inbox)
        # Only accepted pause requests own dispatch holds. Admission holds must
        # remain releasable even when a later pause supersedes a dispatch pause.
        self.hold_id = None
        for event in journal.read():
            body = event.body
            if (event.type == "signal" and body.get("kind") == "control_decision"
                    and body.get("outcome") == "accepted"):
                request = body.get("request") or {}
                if request.get("action") == "pause":
                    hold_id = UUID(request["request_id"])
                    if hold_id in inbox.holds:
                        self.hold_id = hold_id
        self.admission_hold = AdmissionHold(inbox, journal)
        self.storm_hold = StormDispatchHold(inbox, journal)

    async def allow_offer(self, stem=None):
        allowed = await super().allow_offer(stem)
        return allowed and (stem is None or not self.storm_hold.holds_offer(stem))

    def holds_offer(self, stem):
        return self.storm_hold.holds_offer(stem)

    async def apply(self, request):
        await super().apply(request)
        await self.admission_hold.apply(request)
        await self.storm_hold.apply(request)


def _control_factory(state_dir: Path, config_supplier,
                     sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                     poll_sleep: Callable[[float], Awaitable[None]] = asyncio.sleep):
    fs = LocalFilesystem()
    sessions = {}

    def factory(journal: Journal):
        if journal in sessions:
            return sessions[journal]
        # Runner has acquired the lock before exposing this journal.
        holder = Holder(**json.loads(fs.read(state_dir / LOCK_NAME)))
        inbox = compose_daemon_control(state_dir=state_dir, journal=journal, fs=fs,
                                       holder=holder)
        pause = _AdmissionDispatchPause(inbox, journal)

        async def wait_for_control() -> None:
            await inbox.consume(pause.apply)
            await sleep(1)

        async def poll_for_control() -> None:
            requests = []
            for path in fs.list(state_dir / "control", "*.json"):
                try:
                    requests.append(ControlRequest.model_validate_json(fs.read(path)))
                except ValueError:
                    continue
            if any(request.action == "kill" for request in requests):
                await inbox.consume(pause.apply)
            await poll_sleep(.05)

        pause.bind_dispatch_control(poll_for_control)

        async def work(_stem, _captured) -> None:
            raise RuntimeError("the bootstrap drain owns dispatch observations")

        graph = compose_daemon_dispatch(
            config_supplier, work, pause=pause, wait_for_control=wait_for_control)
        sessions[journal] = graph.pause, wait_for_control
        return sessions[journal]
    return factory


def _control(args, cwd: Path, env, out: TextIO, pipeline, clock, process) -> int:
    """Publish to the live holder, or become the short-lived direct holder."""
    config = _config(args, cwd)
    state_dir = cwd / config.state_dir
    lock = Lockfile(state_dir, instance_id="control", clock=clock)
    try:
        lock.acquire()
    except LockHeld as held:
        lifecycle = _published_lifecycle(state_dir, held.holder)
        if lifecycle is None:
            raise Refusal("the lock holder is not a live drain control consumer",
                          "wait for its next control boundary, then repeat the command") from None
        request = _control_request(args, lifecycle)
        publish_control(state_dir, request, LocalFilesystem())
        if args.verb == "kill":
            print("published kill", file=out)
        else:
            hold_id = request.request_id if args.verb == "pause" else args.hold_id
            print(f"published {args.verb}: hold id {hold_id}", file=out)
        return EXIT_OK
    try:
        if args.verb == "kill":
            raise Refusal("nothing running to kill",
                          "start `squatch drain`, then repeat the command")
        with Journal(state_dir, clock=clock) as journal:
            inbox = compose_daemon_control(state_dir=state_dir, journal=journal,
                                           fs=LocalFilesystem())
            pause = _AdmissionDispatchPause(inbox, journal)
            request = _control_request(args, inbox.lifecycle)
            publish_control(state_dir, request, LocalFilesystem())
            decisions = asyncio.run(inbox.consume(pause.apply))
            decision = next(item for item in decisions if item.request == request)
            if decision.outcome != "accepted":
                raise Refusal(f"{args.verb}: {decision.reason or decision.outcome}",
                              "check the active hold id, then repeat the command")
            hold_id = request.request_id if args.verb == "pause" else args.hold_id
            print(f"applied {args.verb}: hold id {hold_id}", file=out)
        return EXIT_OK
    finally:
        lock.release()


def _control_request(args, lifecycle: UUID) -> ControlRequest:
    if args.verb == "pause":
        return ControlRequest(action="pause", lifecycle=lifecycle)
    if args.verb == "kill":
        return ControlRequest(action="kill", lifecycle=lifecycle)
    return ControlRequest(action="release", lifecycle=lifecycle, hold_id=args.hold_id)


def _published_lifecycle(state_dir: Path, holder: Holder | None) -> UUID | None:
    if holder is None:
        return None
    for event in reversed(tuple(read_events(state_dir))):
        if event.type == "signal" and event.body.get("kind") == "control_lifecycle":
            if event.body.get("holder") != asdict(holder):
                continue
            try:
                return UUID(event.body["lifecycle"])
            except (KeyError, TypeError, ValueError):
                return None
    return None


def _triage(args, cwd: Path, env, out: TextIO, pipeline, clock, process) -> int:
    return _locked(args, cwd, env, out, pipeline, clock, process,
                   lambda runner, config, git, control: _triage_pass(
                       runner, config, git, cwd, env, out, clock, process))


async def _triage_pass(runner: Runner, config, git: Git, cwd: Path, env,
                       out: TextIO, clock: Clock, process: ProcessExec) -> int:
    async with runner.session() as session:
        state = cwd / config.state_dir
        fs = LocalFilesystem()
        redact = Redactor.from_config(config, env)
        try:
            registry = Registry(config)
        except ConfigError as e:
            raise Refusal(f"config: {e}",
                          "fix the named provider or routing row in config.yaml") from None
        client = CliClient(registry, process=process, fs=fs, env=env,
                           redact=redact, state_dir=state, cwd=cwd)
        consumer = Triage(
            repo=cwd, config=config, git=git, fs=fs, clock=clock, journal=session.journal,
            llm=client, log=EngineLog(state, clock=clock, redact=redact), redact=redact,
            report=lambda line: print(line, file=out))
        await consumer.run(load_spec(ENGINE_ROOT / "specs" / "triage.md"))
    return EXIT_OK


class _RestartRunner(Runner):
    def session(self):
        restarted = compose_daemon_restart(session=super().session(), clock=self._clock)

        @asynccontextmanager
        async def active():
            async with restarted as session:
                with compose_daemon_storm_producer(
                        state_dir=self.state_dir, journal=session.journal,
                        fs=self._fs, clock=self._clock):
                    yield session

        return active()


def _locked(args, cwd: Path, env, out: TextIO, pipeline: PipelineFactory | None, clock: Clock,
            process: ProcessExec, verb) -> int:
    """The two scaffold verbs' shared composition: config, git, engine log,
    the runner over the stage-dispatch factory; `verb` runs under its lock."""
    def config_supplier():
        return _config(args, cwd)

    config = config_supplier()
    # Inherit-minus-secrets: git never needs a provider key (section 6).
    git = Git(process, env=child_env(env, {p.auth for p in config.providers if p.auth}),
              timeout=GIT_TIMEOUT_SECONDS)

    control = _control_factory(cwd / config.state_dir, config_supplier)

    serve_pipelines = {}

    def factory(journal):
        if getattr(args, "verb", None) == "serve" and journal in serve_pipelines:
            return serve_pipelines[journal]
        if pipeline is not None:  # a scripted stand-in (tests)
            composed = pipeline(journal)
        else:
            pause, _wait = control(journal)
            composed = compose_pipeline(repo=cwd, config=config, env=env, journal=journal,
                                        clock=clock, process=process, fs=LocalFilesystem(), git=git,
                                        control_inbox=pause.inbox,
                                        admission_hold=pause.admission_hold)
            if getattr(args, "verb", None) == "drain":
                pause.bind_abort(composed.stages.abort_active)
        if getattr(args, "verb", None) == "serve":
            serve_pipelines[journal] = composed
        return composed

    async def go() -> int:
        try:
            instance_id = await git.describe(ENGINE_ROOT)
        except ExecutableNotFound:
            raise Refusal("git is not on PATH", "install git; every git call is an argv "
                          "subprocess through git.py") from None
        log = EngineLog(cwd / config.state_dir, clock=clock,
                        redact=Redactor.from_config(config, env))
        runner = _RestartRunner(repo=cwd, config=config, git=git, fs=LocalFilesystem(), clock=clock,
                        instance_id=instance_id, pipeline=factory, log=log,
                        report=lambda line: print(line, file=out))
        return await verb(runner, config, git, control)

    try:
        return asyncio.run(go())
    except GitError as e:
        raise Refusal(f"git: {e}", "inspect the checkout; the failing argv is in the message") from None


def _config(args, cwd: Path):
    try:
        return load(args.config, cwd=cwd)
    except ConfigError as e:
        raise Refusal(f"config: {e}", "fix the named key in config.yaml (section 15)") from None


if __name__ == "__main__":
    sys.exit(main())
