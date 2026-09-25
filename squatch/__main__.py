"""`python -m squatch <verb>`: the module entry (SQUATCH_PLAN.md section 18).

stdlib argparse, the bootstrap verbs -- `status`, `new <stem>`, `run <stem>`,
`drain [--parked <stem>]...`, and `triage` -- plus the section 18 exit-code contract: 0
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
import os
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

import squatch
from squatch.box import BoxCorruption
from squatch.config import ConfigError, load
from squatch.drain import Drain
from squatch.enginelog import EngineLog
from squatch.git import Git, GitError
from squatch.journal import JournalCorruption, read_events
from squatch.providers import CliClient, Registry, child_env
from squatch.redact import Redactor
from squatch.merge import compose_pipeline
from squatch.runner import EXIT_OK, EXIT_REFUSED, PipelineFactory, Refusal, Runner
from squatch.seams import (Clock, ExecutableNotFound, LocalFilesystem, ProcessExec,
                           SubprocessExec)
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
                "reject": _reject, "drain": _drain, "triage": _triage}[args.verb](
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
                   lambda runner, config, git: runner.run(args.stem))


def _confirm(args, cwd: Path, env, out: TextIO, pipeline, clock, process) -> int:
    return _locked(args, cwd, env, out, pipeline, clock, process,
                   lambda runner, config, git: runner.confirm(args.stem))


def _reject(args, cwd: Path, env, out: TextIO, pipeline, clock, process) -> int:
    return _locked(args, cwd, env, out, pipeline, clock, process,
                   lambda runner, config, git: runner.reject(args.stem))


def _drain(args, cwd: Path, env, out: TextIO, pipeline, clock, process) -> int:
    return _locked(args, cwd, env, out, pipeline, clock, process,
                   lambda runner, config, git: Drain(
                       runner=runner, repo=cwd, config=config, git=git, clock=clock,
                       process=process, env=env, config_path=args.config,
                       carried=args.parked,
                       report=lambda line: print(line, file=out)).run())


def _triage(args, cwd: Path, env, out: TextIO, pipeline, clock, process) -> int:
    return _locked(args, cwd, env, out, pipeline, clock, process,
                   lambda runner, config, git: _triage_pass(
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


def _locked(args, cwd: Path, env, out: TextIO, pipeline: PipelineFactory | None, clock: Clock,
            process: ProcessExec, verb) -> int:
    """The two scaffold verbs' shared composition: config, git, engine log,
    the runner over the stage-dispatch factory; `verb` runs under its lock."""
    config = _config(args, cwd)
    # Inherit-minus-secrets: git never needs a provider key (section 6).
    git = Git(process, env=child_env(env, {p.auth for p in config.providers if p.auth}),
              timeout=GIT_TIMEOUT_SECONDS)

    def factory(journal):
        if pipeline is not None:  # a scripted stand-in (tests)
            return pipeline(journal)
        return compose_pipeline(repo=cwd, config=config, env=env, journal=journal, clock=clock,
                                process=process, fs=LocalFilesystem(), git=git)

    async def go() -> int:
        try:
            instance_id = await git.describe(ENGINE_ROOT)
        except ExecutableNotFound:
            raise Refusal("git is not on PATH", "install git; every git call is an argv "
                          "subprocess through git.py") from None
        log = EngineLog(cwd / config.state_dir, clock=clock,
                        redact=Redactor.from_config(config, env))
        runner = Runner(repo=cwd, config=config, git=git, fs=LocalFilesystem(), clock=clock,
                        instance_id=instance_id, pipeline=factory, log=log,
                        report=lambda line: print(line, file=out))
        return await verb(runner, config, git)

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
