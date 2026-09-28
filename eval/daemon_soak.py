"""Run and write the bounded daemon-soak report."""

import asyncio
import json
import os
import sys
import tempfile
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

from squatch.artifacts import (DAEMON_SOAK_MEMBERS, DAEMON_SOAK_REPORT, DaemonSoakEntry,
                               DaemonSoakReport)
from squatch.audit import audit_journal
from squatch.box import Box
from squatch.config import Config, parse
from squatch.control import ControlRequest, publish_control
from squatch.daemon import DispatchPause, compose_daemon_control
from squatch.enginelog import EngineLog
from squatch.git import Git
from squatch.journal import Event, Journal, read_events
from squatch.merge import compose_pipeline
from squatch.mergequeue import AdmissionHold
from squatch.providers import Registry
from squatch.redact import Redactor
from squatch.__main__ import _RestartRunner
from squatch.seams import Filesystem, LocalFilesystem, ProcessExec, SubprocessExec
from squatch.serve import CONTROL_POLL_SECONDS, Serve

REPORT_NAME = DAEMON_SOAK_REPORT
_SOAK_HOURS = 24
_TICK = timedelta(hours=1)
_STEMS = {
    "worker_killed_mid_run": "worker-killed-mid-run",
    "conflict_resolution_rungs": "conflict-resolution-rungs",
    "semantic_conflict_integration_red": "semantic-conflict-integration-red",
}
_FAULTS: Mapping[str, tuple[str, str, str]] = {
    "worker_killed_mid_run": (
        "kill a production-dispatched worker while its provider process is active",
        "the recovery alert, abandoned run, and clean re-dispatched terminal",
        "recovery_alert:abandoned->merged;redispatched=1"),
    "conflict_resolution_rungs": (
        "plant two real Git conflicts, one union-resolvable and one unresolved",
        "the production conflict facts while main stays at its green pre-admission tree",
        "mechanical->rework;main=green"),
    "semantic_conflict_integration_red": (
        "fail the real post-rebase integration command through the process seam",
        "the production integration-red terminal while main stays green and unchanged",
        "integration_red:verification;main=green"),
}


class AdvancingClock(Protocol):
    """An aware injected clock whose passage is controlled by the soak."""

    def __call__(self) -> datetime: ...

    def advance(self, elapsed: timedelta) -> None: ...


class DeterministicClock:
    """The shipped wall-clock-free clock for a reproducible soak."""

    def __init__(self, now: datetime | None = None) -> None:
        self.now = now or datetime(2026, 1, 1, tzinfo=timezone.utc)
        if self.now.tzinfo is None or self.now.utcoffset() is None:
            raise ValueError("daemon-soak clock requires an aware datetime")

    def __call__(self) -> datetime:
        return self.now

    def advance(self, elapsed: timedelta) -> None:
        if elapsed < timedelta(0):
            raise ValueError("daemon-soak clock cannot move backwards")
        self.now += elapsed


class _InjectedSleep:
    """Advance one bounded tick whenever the live graph traverses its sleep seam."""

    def __init__(self, clock: AdvancingClock) -> None:
        self._clock = clock
        self.started_at = clock()
        self.reached = asyncio.Event()
        self._released = asyncio.Event()
        self.advances: list[timedelta] = []

    async def __call__(self, seconds: float) -> None:
        if self.elapsed < timedelta(hours=_SOAK_HOURS):
            remaining = timedelta(hours=_SOAK_HOURS) - self.elapsed
            elapsed = min(_TICK, remaining)
            self._clock.advance(elapsed)
            self.advances.append(elapsed)
            if self.elapsed >= timedelta(hours=_SOAK_HOURS):
                self.reached.set()
        else:
            await self._released.wait()
            if seconds > CONTROL_POLL_SECONDS:
                await asyncio.Future()
        await asyncio.sleep(0)

    @property
    def elapsed(self) -> timedelta:
        return self._clock() - self.started_at

    def release(self) -> None:
        self._released.set()


def _config() -> Config:
    return parse({
        "schema_version": 1,
        "state_dir": ".state",
        "providers": [{
            "name": "codex", "kind": "cli",
            "models_by_tier": dict.fromkeys(("low", "medium", "high", "max"), "soak"),
            "limits": {"concurrency": 1, "est_cost_per_call_usd": 0},
        }],
        "routing": [{
            "tier": "medium", "surface": "review",
            "candidates": [{"provider": "codex"}],
        }],
        "caps": {"diagnosis": 1, "retry": 0},
        "merge": {"strategies": [{"paths": ["shared.txt"], "strategy": "union"}]},
    }, source="daemon-soak")


def _ticket(stem: str) -> str:
    return f"""---
state: confirmed
source: human
priority: P1
kind: feature
---
## Depends on
- none

## Context
- shared.txt

## Goal
Exercise the production daemon fault for {stem}.

## Why
The bounded daemon soak needs member-local production evidence.

## Scope in
Change only the planted fault fixture.

## Scope out
Do not change the ticket plane.

## Scope fence
- feature.txt
- shared.txt
- manual.txt

## Acceptance criteria
- The planted daemon fault is observed while `shared.txt` remains in the fixture.

## Verification
```
{sys.executable} -c "raise SystemExit(0)"
```

## Definition of rejected
Reject evidence not produced by the production graph.

## Time budget
- expected: 1m
- stuck: 2m
"""


def _run_record(member: str) -> str:
    bodies = {
        "Outcome": "ok",
        "Surprises / judgment calls": "",
        "Dead ends": "",
        "Second problems filed": f"- daemon soak fault observed: {member}",
        "Resolved engine/model": "codex/soak",
        "Predicted vs actual": "1m / injected execution",
    }
    return "".join(f"## {heading}\n{body}\n\n" for heading, body in bodies.items())


def _codex_result(payload: dict) -> str:
    text = json.dumps(payload)
    return "\n".join((
        json.dumps({"type": "item.completed",
                    "item": {"type": "agent_message", "text": text}}),
        json.dumps({"type": "turn.completed", "usage": {}}),
    )) + "\n"


class _ScenarioProcess:
    """A faulting host process behind the production process boundary."""

    def __init__(self, *, member: str, repo: Path, env: Mapping[str, str],
                 fs: Filesystem, process: ProcessExec) -> None:
        self.member = member
        self.repo = Path(repo)
        self.env = dict(env)
        self.fs = fs
        self._process = process
        self.git = Git(self, env=self.env, timeout=60)
        self.fault_ready = asyncio.Event()
        self._implement_calls = 0
        self._verification_calls = 0
        self.main_after_fault: str | None = None

    async def run(self, argv: Sequence[str], *, cwd: Path, env: Mapping[str, str],
                  timeout: float | None, stdin_path: Path | None = None,
                  on_spawn=None) -> tuple[int, str, str]:
        if argv and argv[0] == "codex":
            assert stdin_path is not None
            surface = stdin_path.name.split("-", 2)[1]
            return await self._model(surface, Path(cwd))
        if argv and argv[0] == "git" and argv[-1] == "push":
            return 0, "", ""
        if argv and argv[0] == sys.executable:
            self._verification_calls += 1
            # The production stages run this argv once at Check, once during
            # post-rebase regate, and once as the queue's integration check.
            if (self.member == "semantic_conflict_integration_red"
                    and self._verification_calls == 3):
                return 1, "", "planted semantic integration failure"
        return await self._process.run(
            argv, cwd=cwd, env=env, timeout=timeout, stdin_path=stdin_path,
            on_spawn=on_spawn)

    async def _model(self, surface: str, cwd: Path) -> tuple[int, str, str]:
        if surface == "implement":
            self._implement_calls += 1
            await self._implement(cwd)
            if self.member == "worker_killed_mid_run" and self._implement_calls == 1:
                self.fault_ready.set()
                await asyncio.Future()
            self.fault_ready.set()
            return 0, _codex_result({"verdict": "implemented", "summary": "fault planted"}), ""
        if surface == "review":
            return 0, _codex_result({
                "verdict": "approve", "summary": "production fault fixture approved",
                "findings": []}), ""
        if surface == "diagnose":
            return 0, _codex_result({
                "verdict": "abandon-human", "lessons": ("retain the soak evidence",),
                "reason": "the planted fault reached its expected terminal"}), ""
        if surface == "triage":
            return 0, _codex_result({
                "verdict": "decision", "reopen_after_days": 1,
                "rationale": "bounded daemon-soak evidence", "evidence": "local run"}), ""
        if surface == "rework":
            await asyncio.Future()
        raise AssertionError(f"unexpected daemon-soak model surface {surface!r}")

    async def _implement(self, worktree: Path) -> None:
        stem = _STEMS[self.member]
        record = worktree / "tickets" / stem / "run.md"
        self.fs.write(record, _run_record(self.member).encode())
        if self.member == "conflict_resolution_rungs":
            self.fs.write(worktree / "shared.txt", b"start\nbranch\n")
            await self.git.add(worktree, ["shared.txt"])
            await self.git.commit(worktree, "candidate shared conflict", ["shared.txt"])
            self.fs.write(worktree / "manual.txt", b"start\nbranch\n")
            await self.git.add(worktree, ["manual.txt"])
            await self.git.commit(worktree, "candidate unresolved conflict", ["manual.txt"])
            self.fs.write(self.repo / "shared.txt", b"start\nmain\n")
            self.fs.write(self.repo / "manual.txt", b"start\nmain\n")
            await self.git.add(self.repo, ["shared.txt", "manual.txt"])
            self.main_after_fault = await self.git.commit(
                self.repo, "advance main into both conflicts", ["shared.txt", "manual.txt"])
            return

        self.fs.write(worktree / "feature.txt", f"{self.member}\n".encode())
        if self.member == "worker_killed_mid_run":
            self.fs.write(
                worktree / "feature.txt",
                f"{self.member} run {self._implement_calls}\n".encode())
        await self.git.add(worktree, ["feature.txt"])
        await self.git.commit(worktree, "candidate fault fixture", ["feature.txt"])
        if self.member == "semantic_conflict_integration_red":
            self.fs.write(self.repo / "shared.txt", b"start\nmain\n")
            await self.git.add(self.repo, ["shared.txt"])
            self.main_after_fault = await self.git.commit(
                self.repo, "advance main before integration", ["shared.txt"])


class _Evidence:
    def __init__(self, *, member: str, state: Path, events: tuple[Event, ...],
                 fs: Filesystem, clock: AdvancingClock,
                 lifetimes: tuple[timedelta, ...], main_after_fault: str | None,
                 main_changes: tuple[str, ...]) -> None:
        self.member = member
        self.state = Path(state)
        self.events = events
        self.fs = fs
        self.clock = clock
        self.lifetimes = lifetimes
        self.main_after_fault = main_after_fault
        self.main_changes = main_changes


def _git_env(env: Mapping[str, str]) -> dict[str, str]:
    return {
        **env,
        "PATH": env.get("PATH", os.environ.get("PATH", "")),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "squatch",
        "GIT_AUTHOR_EMAIL": "squatch@daemon-soak",
        "GIT_COMMITTER_NAME": "squatch",
        "GIT_COMMITTER_EMAIL": "squatch@daemon-soak",
    }


async def _prepare_repo(*, root: Path, member: str, fs: Filesystem,
                        process: ProcessExec, env: Mapping[str, str]):
    config_text = json.dumps(_config().model_dump(mode="json"), default=str) + "\n"
    fs.write(root / "config.yaml", config_text.encode())
    child_env = _git_env(env)
    scenario_process = _ScenarioProcess(
        member=member, repo=root, env=child_env, fs=fs, process=process)
    git = scenario_process.git
    await git.init(root)
    stem = _STEMS[member]
    files = {
        "config.yaml": config_text,
        "SQUATCH_PLAN.md": "# daemon soak host\n",
        "shared.txt": "start\n",
        "manual.txt": "start\n",
        f"tickets/{stem}/ticket.md": _ticket(stem),
    }
    for relative, content in files.items():
        fs.write(root / relative, content.encode())
    await git.add(root, tuple(files))
    await git.commit(root, "daemon soak fixture", tuple(files))
    return _config(), child_env, scenario_process, git


async def _wait_for_terminal(state: Path, stem: str, run_seq: int) -> None:
    for _ in range(10_000):
        if any(event.ticket == stem and event.type == "state_transition"
               and event.body.get("to") not in {None, "running"}
               and event.body.get("run_seq") == run_seq
               for event in read_events(state)):
            return
        await asyncio.sleep(0)
    raise RuntimeError(f"production serve did not terminalize {stem}/{run_seq}")


async def _stop_after_soak(*, serve: Serve, task: asyncio.Task[int],
                           sleeper: _InjectedSleep, state: Path,
                           fs: Filesystem) -> timedelta:
    await asyncio.wait_for(sleeper.reached.wait(), 10)
    if task.done():
        await task
        raise RuntimeError("production serve stopped before the injected soak elapsed")
    if serve.graph is None:
        raise RuntimeError("production serve never exposed its composed graph")
    publish_control(
        state, ControlRequest(action="kill", lifecycle=serve.graph.control.lifecycle), fs)
    sleeper.release()
    await asyncio.wait_for(task, 10)
    return sleeper.elapsed


async def _member(*, member: str, root: Path, clock: AdvancingClock,
                  fs: Filesystem, process: ProcessExec,
                  env: Mapping[str, str]) -> _Evidence:
    config, child_env, scenario_process, git = await _prepare_repo(
        root=root, member=member, fs=fs, process=process, env=env)
    state = root / config.state_dir
    controls = {}
    pipelines = {}
    runner = None

    def control(journal: Journal):
        if journal not in controls:
            inbox = compose_daemon_control(state_dir=state, journal=journal, fs=fs)
            controls[journal] = (DispatchPause(inbox), _cooperate)
        return controls[journal]

    def pipeline(journal: Journal):
        if journal not in pipelines:
            pause, _ = control(journal)
            made = compose_pipeline(
                repo=root, config=config, env=child_env, journal=journal, clock=clock,
                process=scenario_process, fs=fs, git=git, control_inbox=pause.inbox,
                admission_hold=AdmissionHold(pause.inbox, journal),
                providers=runner.providers)
            pipelines[journal] = made
        return pipelines[journal]

    log = EngineLog(state, clock=clock, redact=Redactor.from_config(config, child_env))
    runner = _RestartRunner(
        provider_registry=Registry(config), repo=root, config=config, git=git, fs=fs,
        clock=clock,
        instance_id=f"daemon-soak-{member}", pipeline=pipeline, log=log,
        report=lambda _line: None)
    lifetimes: list[timedelta] = []

    def start() -> tuple[Serve, _InjectedSleep, asyncio.Task[int]]:
        sleeper = _InjectedSleep(clock)
        serve = Serve(
            runner=runner, repo=root, config_supplier=lambda: config, pipeline=pipeline,
            control=control, git=git, fs=fs, clock=clock, process=scenario_process,
            env=child_env, report=lambda _line: None, sleep=sleeper)
        return serve, sleeper, asyncio.create_task(serve.run())

    serve, sleeper, task = start()
    try:
        ready = asyncio.create_task(scenario_process.fault_ready.wait())
        done, _ = await asyncio.wait((ready, task), timeout=10,
                                     return_when=asyncio.FIRST_COMPLETED)
        if task in done:
            ready.cancel()
            await asyncio.gather(ready, return_exceptions=True)
            await task
            raise RuntimeError("production serve stopped before its fault was injected")
        if ready not in done:
            ready.cancel()
            await asyncio.gather(ready, return_exceptions=True)
            raise TimeoutError(f"production serve did not reach {member}")
        if member != "worker_killed_mid_run":
            await _wait_for_terminal(state, _STEMS[member], 0)
        lifetimes.append(await _stop_after_soak(
            serve=serve, task=task, sleeper=sleeper, state=state, fs=fs))
    finally:
        if not task.done():
            sleeper.release()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    if member == "worker_killed_mid_run":
        serve, sleeper, task = start()
        try:
            await _wait_for_terminal(state, _STEMS[member], 1)
            lifetimes.append(await _stop_after_soak(
                serve=serve, task=task, sleeper=sleeper, state=state, fs=fs))
        finally:
            if not task.done():
                sleeper.release()
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    events = tuple(read_events(state))
    main_after = await git.rev_parse(root, "main")
    main_changes = (() if scenario_process.main_after_fault is None else tuple(
        await git.diff_names(root, scenario_process.main_after_fault, main_after)))
    return _Evidence(
        member=member, state=state, events=events, fs=fs, clock=clock,
        lifetimes=tuple(lifetimes), main_after_fault=scenario_process.main_after_fault,
        main_changes=main_changes)


async def _cooperate() -> None:
    await asyncio.sleep(0)


def _producing_event(evidence: _Evidence) -> Event:
    if evidence.member == "worker_killed_mid_run":
        return next(event for event in evidence.events
                    if event.type == "signal"
                    and event.body.get("kind") == "recovery_alert")
    return next(event for event in evidence.events
                if event.type == "signal"
                and event.body.get("kind") == "merge_conflict_facts")


def _passed_invoice(evidence: _Evidence, step: str, stem: str, run_seq: int) -> bool:
    event = next((item for item in evidence.events
                  if item.type == "effect_completion"
                  and item.key == f"{step}/{stem}/{run_seq}"), None)
    if event is None:
        return False
    result = event.body.get("result")
    invoice = result.get("invoice") if step == "check" and isinstance(result, dict) else result
    checks = invoice.get("checks") if isinstance(invoice, dict) else None
    return isinstance(checks, list) and not any(
        check.get("verdict") == "fail" and check.get("severity") == "hard"
        for check in checks if isinstance(check, dict))


def _entry(evidence: _Evidence) -> DaemonSoakEntry:
    member = evidence.member
    event = _producing_event(evidence)
    run_seq = (event.body["run_seq"] if member == "worker_killed_mid_run"
               else int(event.key.rsplit("/", 1)[1]))
    if member == "worker_killed_mid_run":
        abandoned = next(item for item in evidence.events
                         if item.ticket == event.ticket
                         and item.type == "state_transition"
                         and item.body.get("run_seq") == 0
                         and item.body.get("to") == "abandoned")
        redispatched = next(item for item in evidence.events
                            if item.ticket == event.ticket
                            and item.type == "state_transition"
                            and item.body.get("run_seq") == run_seq + 1
                            and item.body.get("to") not in {None, "running"})
        observed = (f"{event.body['kind']}:{abandoned.body['to']}->"
                    f"{redispatched.body['to']};redispatched={redispatched.body['run_seq']}")
    elif member == "conflict_resolution_rungs":
        rungs = ("mechanical->rework"
                 if event.body["strategy_hits"] and event.body["rung"] == "rework"
                 else str(event.body["rung"]))
        main = ("green" if _passed_invoice(evidence, "check", event.ticket, run_seq)
                and evidence.main_after_fault is not None
                and all(path.startswith("tickets/") for path in evidence.main_changes)
                else "red")
        observed = f"{rungs};main={main}"
    else:
        terminal = next(item for item in evidence.events
                        if item.ticket == event.ticket and item.type == "state_transition"
                        and item.body.get("run_seq") == run_seq
                        and item.body.get("to") == "gate_failed")
        main = ("green" if _passed_invoice(evidence, "check", event.ticket, run_seq)
                and _passed_invoice(evidence, "regate", event.ticket, run_seq)
                and evidence.main_after_fault is not None
                and all(path.startswith("tickets/") for path in evidence.main_changes)
                else "red")
        observed = ("integration_red:" + ",".join(terminal.body["finding_codes"])
                    + f";main={main}")

    message = Box(evidence.state, fs=evidence.fs, clock=evidence.clock).by_origin(event.ticket)
    if (member == "worker_killed_mid_run"
            and event.body.get("disposition") == "alert"
            and event.body.get("outcome") == "abandoned"):
        disposition = "alert"
    elif message is not None and message.run_seq == run_seq:
        disposition = "box"
    elif any(item.type == "signal" and item.ticket == event.ticket
             and item.body.get("kind") == "escalation"
             and item.body.get("run_seq") == run_seq
             for item in evidence.events):
        disposition = "alert"
    else:
        raise RuntimeError(f"{member} produced neither member-local Box nor alert evidence")
    fault, observable, expected = _FAULTS[member]
    auditor = "red" if audit_journal(evidence.state) else "green"
    return DaemonSoakEntry(
        member=member, fault=fault, observable=observable, expected=expected,
        observed=observed, disposition=disposition,
        producing_run=f"{event.ticket}/{run_seq}", auditor=auditor,
        green=observed == expected and auditor == "green")


def _elapsed_hours(evidence: Sequence[_Evidence]) -> float:
    lifetimes = [elapsed for item in evidence for elapsed in item.lifetimes]
    if not lifetimes:
        raise RuntimeError("daemon soak produced no serve lifecycle evidence")
    return min(elapsed.total_seconds() / 3600 for elapsed in lifetimes)


async def _run(*, repo: Path, root: Path, clock: AdvancingClock,
               fs: Filesystem, process: ProcessExec,
               env: Mapping[str, str]) -> DaemonSoakReport:
    if tuple(_FAULTS) != DAEMON_SOAK_MEMBERS:
        raise ValueError("daemon-soak scenario registry differs from its closed schema")
    evidence = [await _member(
        member=member, root=root / member, clock=clock, fs=fs,
        process=process, env=env) for member in DAEMON_SOAK_MEMBERS]
    produced_at_sha = await Git(process, env=env, timeout=60).rev_parse(Path(repo), "HEAD")
    return DaemonSoakReport(
        schema_version=1, produced_at_sha=produced_at_sha,
        injected_hours=_elapsed_hours(evidence),
        entries=tuple(_entry(item) for item in evidence))


def run(*, repo: Path, evidence_root: Path | None = None,
        clock: AdvancingClock | None = None, fs: Filesystem | None = None,
        process: ProcessExec | None = None,
        env: Mapping[str, str] | None = None) -> DaemonSoakReport:
    """Run the closed scenarios and return their report without writing it."""
    clock = clock or DeterministicClock()
    fs = fs or LocalFilesystem()
    process = process or SubprocessExec()
    env = dict(os.environ if env is None else env)
    if evidence_root is not None:
        return asyncio.run(_run(
            repo=repo, root=Path(evidence_root), clock=clock, fs=fs,
            process=process, env=env))
    with tempfile.TemporaryDirectory(prefix="squatch-daemon-soak-") as temporary:
        return asyncio.run(_run(
            repo=repo, root=Path(temporary), clock=clock, fs=fs,
            process=process, env=env))


def dumps(report: DaemonSoakReport) -> str:
    """Return the byte-stable representation used by ordinary-lane custody."""
    return json.dumps(report.model_dump(mode="json"), sort_keys=True, indent=2) + "\n"


def write_report(*, workspace: Path, stem: str, report: DaemonSoakReport,
                 fs: Filesystem) -> Path:
    """Leave a validated report for the stage-terminal ordinary lane to lift."""
    if not stem or Path(stem).name != stem:
        raise ValueError("stem must be one non-empty path component")
    # Validate a copy at the write boundary so subclasses or unvalidated input
    # cannot bypass the same closed contract the ordinary lane applies.
    data = dumps(DaemonSoakReport.model_validate(report.model_dump(mode="json"))).encode()
    destination = Path(workspace) / "tickets" / stem / REPORT_NAME
    fs.write(destination, data)
    return destination
