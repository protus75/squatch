"""`python -m squatch <verb>`: the module entry (SQUATCH_PLAN.md section 18).

stdlib argparse, the Phase 1 verbs -- `status`, `new <stem>`, `run <stem>`,
`drain` -- and the section 18 exit-code contract: 0 settled or quiescent, 1 a
non-ok ticket terminal or a ceiling-halted drain, 2 an engine-plane refusal.
Nothing reaches the operator as a raw traceback: every refusal prints its
message and paved road. The checkout root is the invocation cwd; `--config`
relocates only the config file. The project stays virtual: this module entry
is the whole CLI surface until the release path (section 13 touchpoint 6)
earns a console script.
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
from squatch.config import ConfigError, load
from squatch.drain import Drain
from squatch.enginelog import EngineLog
from squatch.git import Git, GitError
from squatch.journal import JournalCorruption, read_events
from squatch.providers import child_env
from squatch.redact import Redactor
from squatch.merge import compose_pipeline
from squatch.runner import EXIT_REFUSED, PipelineFactory, Refusal, Runner
from squatch.seams import Clock, ExecutableNotFound, LocalFilesystem, SubprocessExec
from squatch.status import project, render
from squatch.tickets import new_ticket

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
    sub.add_parser("drain", help="run every eligible ticket, one at a time, to quiescence")
    return p


def main(argv: Sequence[str] | None = None, *, cwd: Path | None = None,
         env: Mapping[str, str] | None = None, out: TextIO | None = None,
         pipeline: PipelineFactory | None = None, clock: Clock = _now) -> int:
    """`pipeline` and `clock` are the test seams: a scripted stage-dispatch
    factory over the lock-held journal, and the clock every verb reads."""
    out = out if out is not None else sys.stdout
    cwd = Path(cwd) if cwd is not None else Path.cwd()
    env = dict(env if env is not None else os.environ)
    try:
        args = _parser().parse_args(argv)
    except SystemExit as e:  # argparse already printed usage or help
        return int(e.code or 0)
    try:
        return {"status": _status, "new": _new, "run": _run, "drain": _drain}[args.verb](
            args, cwd, env, out, pipeline, clock)
    except Refusal as e:
        print(f"refused: {e.message}", file=out)
        print(f"  paved road: {e.paved_road}", file=out)
        return EXIT_REFUSED


def _status(args, cwd: Path, env, out: TextIO, pipeline, clock) -> int:
    config = _config(args, cwd)
    try:
        status = project(read_events(cwd / config.state_dir), repo=cwd)
    except JournalCorruption as e:
        raise Refusal(f"journal corruption: {e}",
                      "a corrupt record is never skipped; inspect the named segment line") from None
    out.write(render(status))
    return 0


def _new(args, cwd: Path, env, out: TextIO, pipeline, clock) -> int:
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


def _run(args, cwd: Path, env, out: TextIO, pipeline, clock) -> int:
    return _locked(args, cwd, env, out, pipeline, clock,
                   lambda runner, config, git: runner.run(args.stem))


def _drain(args, cwd: Path, env, out: TextIO, pipeline, clock) -> int:
    return _locked(args, cwd, env, out, pipeline, clock,
                   lambda runner, config, git: Drain(
                       runner=runner, repo=cwd, config=config, git=git, clock=clock,
                       report=lambda line: print(line, file=out)).run())


def _locked(args, cwd: Path, env, out: TextIO, pipeline: PipelineFactory | None, clock: Clock,
            verb) -> int:
    """The two scaffold verbs' shared composition: config, git, engine log,
    the runner over the stage-dispatch factory; `verb` runs under its lock."""
    config = _config(args, cwd)
    # Inherit-minus-secrets: git never needs a provider key (section 6).
    git = Git(SubprocessExec(), env=child_env(env, {p.auth for p in config.providers if p.auth}),
              timeout=GIT_TIMEOUT_SECONDS)

    def factory(journal):
        if pipeline is not None:  # a scripted stand-in (tests)
            return pipeline(journal)
        return compose_pipeline(repo=cwd, config=config, env=env, journal=journal, clock=clock,
                                process=SubprocessExec(), fs=LocalFilesystem(), git=git)

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
