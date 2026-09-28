"""Execute deterministic provider faults and return closed reliability evidence."""

import asyncio
import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path

from squatch.artifacts import (RELIABILITY_BATTERY_MEMBERS, ReliabilityBatteryEntry,
                               ReliabilityBatteryReport)
from squatch.audit import audit_journal
from squatch.config import parse
from squatch.git import Git
from squatch.journal import Journal, JournalCorruption, read_events
from squatch.llm import LLMRequest
from squatch.providers import CliClient, ProviderError, ProviderRuntime, Registry
from squatch.redact import Redactor
from squatch.seams import Filesystem, LocalFilesystem, ProcessExec, SubprocessExec
from squatch.timers import Timers


class DeterministicClock:
    """A mutable clock whose movement is wholly controlled by the battery."""

    def __init__(self, now: datetime | None = None) -> None:
        self.now = now or datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, elapsed: timedelta) -> None:
        if elapsed < timedelta(0):
            raise ValueError("reliability battery clock cannot move backwards")
        self.now += elapsed


class _FaultProcess:
    """A process seam whose queued outcomes are the deliberate boundary faults."""

    def __init__(self, responses: Sequence[tuple[int, str, str]]) -> None:
        self._responses = iter(responses)
        self.calls: list[str] = []

    async def run(self, argv: Sequence[str], *, cwd: Path, env: Mapping[str, str],
                  timeout: float | None, stdin_path: Path | None = None,
                  on_spawn=None, on_stdout_line=None) -> tuple[int, str, str]:
        self.calls.append(argv[0])
        response = next(self._responses)
        if on_stdout_line is not None:
            for line in response[1].splitlines():
                on_stdout_line(line)
        return response


def _config():
    return parse({
        "schema_version": 1, "state_dir": ".state",
        "providers": [
            {"name": "codex", "kind": "cli", "models_by_tier": dict.fromkeys(
                ("low", "medium", "high", "max"), "battery"),
             "limits": {"concurrency": 1, "quota_window_minutes": 60,
                        "est_cost_per_call_usd": 0}},
            {"name": "claude", "kind": "cli", "models_by_tier": dict.fromkeys(
                ("low", "medium", "high", "max"), "battery"),
             "limits": {"concurrency": 1, "quota_window_minutes": 60}},
        ],
        "routing": [{"tier": "medium", "surface": "review",
                     "candidates": [{"provider": "codex"}, {"provider": "claude"}]}],
    }, source="reliability-battery")


def _codex_success() -> str:
    return "\n".join((
        json.dumps({"type": "item.completed", "item": {
            "type": "agent_message", "text": "recovered"}}),
        json.dumps({"type": "turn.completed", "usage": {
            "input_tokens": 1, "output_tokens": 1}}), ""))


def _request() -> LLMRequest:
    return LLMRequest(surface="review", rendered="reliability battery", tier="medium",
                      effort="medium", ticket=None, worktree=None)


async def _call_error(client: CliClient) -> ProviderError | None:
    try:
        await client.call(_request())
    except ProviderError as error:
        return error
    return None


def _failure_class(error: ProviderError | None) -> str:
    return error.failure_class if error is not None else "missing"


def _auditor(root: Path) -> str:
    try:
        if not tuple(read_events(root)):
            return "red"
        return "red" if audit_journal(root) else "green"
    except (FileNotFoundError, JournalCorruption):
        return "red"


def _entry(member: str, expected: str, observed: str, root: Path) -> ReliabilityBatteryEntry:
    auditor = _auditor(root)
    return ReliabilityBatteryEntry(
        member=member, fault="injected provider process failure",
        observable="provider errors, cooldown deadlines, selected candidate, and journal audit",
        expected=expected, observed=observed, auditor=auditor,
        green=observed == expected and auditor == "green")


async def _member(*, member: str, root: Path, clock: DeterministicClock,
                  fs: Filesystem) -> ReliabilityBatteryEntry:
    config = _config()
    scripts = {
        "classified_quota_exhaustion": ((1, "", "You've hit your usage limit"),),
        "all_candidates_cooling_recovery": (
            (1, "", "You've hit your usage limit"),
            (1, "", "You've hit your limit"),
            (0, _codex_success(), "")),
        "unclassified_failure_preservation": ((1, "", "unknown provider failure"),),
    }
    with Journal(root, clock=clock) as journal:
        timers = Timers(journal=journal, clock=clock)
        timers.rearm()
        process = _FaultProcess(scripts[member])
        runtime = ProviderRuntime(Registry(config), timers=timers, clock=clock)
        client = CliClient(runtime, process=process, fs=fs, env={},
                           redact=Redactor.from_config(config, {}), state_dir=root, cwd=root)
        try:
            if member == "classified_quota_exhaustion":
                failure = await _call_error(client)
                deadline = timers.pending(runtime._prefix("codex"))
                observed = (f"failure={_failure_class(failure)};cooldown="
                            f"{deadline.isoformat() if deadline is not None else 'missing'}")
                expected = ("failure=quota_exhausted;cooldown="
                            f"{(clock() + timedelta(minutes=60)).isoformat()}")
            elif member == "all_candidates_cooling_recovery":
                first, second = await _call_error(client), await _call_error(client)
                all_cooling = await _call_error(client)
                clock.advance(timedelta(minutes=60))
                try:
                    recovered = await client.call(_request())
                    provider = recovered.provider
                except ProviderError:
                    provider = "missing"
                observed = (f"first={_failure_class(first)};second={_failure_class(second)};"
                            f"all_cooling={_failure_class(all_cooling)};recovered={provider}")
                expected = ("first=quota_exhausted;second=quota_exhausted;"
                            "all_cooling=quota_exhausted;recovered=codex")
            else:
                failure = await _call_error(client)
                observed = f"failure={_failure_class(failure)};calls={','.join(process.calls)}"
                expected = "failure=unclassified;calls=codex"
            journal.append("signal", {"kind": "reliability_battery_evidence",
                                      "member": member, "observed": observed})
        finally:
            await timers.shutdown()
    return _entry(member, expected, observed, root)


async def _run(*, repo: Path, root: Path, clock: DeterministicClock,
               fs: Filesystem, process: ProcessExec, env: Mapping[str, str]) -> ReliabilityBatteryReport:
    if tuple(RELIABILITY_BATTERY_MEMBERS) != (
            "classified_quota_exhaustion", "all_candidates_cooling_recovery",
            "unclassified_failure_preservation"):
        raise ValueError("reliability scenario registry differs from its closed schema")
    entries = tuple([
        await _member(member=member, root=root / member, clock=clock, fs=fs)
        for member in RELIABILITY_BATTERY_MEMBERS
    ])
    produced_at_sha = await Git(process, env=env, timeout=60).rev_parse(repo, "HEAD")
    return ReliabilityBatteryReport(schema_version=1, produced_at_sha=produced_at_sha,
                                    entries=entries)


def run(*, repo: Path, evidence_root: Path | None = None,
        clock: DeterministicClock | None = None, fs: Filesystem | None = None,
        process: ProcessExec | None = None,
        env: Mapping[str, str] | None = None) -> ReliabilityBatteryReport:
    """Return the report; the ordinary lane remains the only report writer."""
    clock = clock or DeterministicClock()
    fs = fs or LocalFilesystem()
    process = process or SubprocessExec()
    env = dict(os.environ if env is None else env)
    if evidence_root is not None:
        return asyncio.run(_run(repo=Path(repo), root=Path(evidence_root), clock=clock,
                                fs=fs, process=process, env=env))
    with tempfile.TemporaryDirectory(prefix="squatch-reliability-battery-") as temporary:
        return asyncio.run(_run(repo=Path(repo), root=Path(temporary), clock=clock,
                                fs=fs, process=process, env=env))
