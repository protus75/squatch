"""Closed, execution-derived evidence for the provider reliability boundary."""

import asyncio
from pathlib import Path

import pytest
from pydantic import ValidationError

from eval.reliability_battery import DeterministicClock, _auditor, _member, run
from squatch.artifacts import (RELIABILITY_BATTERY_MEMBERS, RELIABILITY_BATTERY_REPORT,
                               ReliabilityBatteryEntry, ReliabilityBatteryReport)
from squatch.providers import ProviderRuntime
from squatch.seams import LocalFilesystem
from squatch.stages import KNOWN_ARTIFACTS


class HeadProcess:
    def __init__(self, sha="a" * 40):
        self.sha = sha
        self.calls = []

    async def run(self, argv, *, cwd, env, timeout, stdin_path=None, on_spawn=None,
                  on_stdout_line=None):
        self.calls.append(list(argv))
        assert argv[-2:] == ["--verify", "HEAD"]
        return 0, self.sha + "\n", ""


def entry(member, **changes):
    values = {"member": member, "fault": "fault", "observable": "evidence",
              "expected": "ok", "observed": "ok", "auditor": "green", "green": True}
    values.update(changes)
    return ReliabilityBatteryEntry(**values)


def report(**changes):
    values = {"schema_version": 1, "produced_at_sha": "a" * 40,
              "entries": tuple(entry(member) for member in RELIABILITY_BATTERY_MEMBERS)}
    values.update(changes)
    return ReliabilityBatteryReport(**values)


def test_closed_report_schema_is_registered_for_ordinary_lane_validation():
    made = report()
    assert KNOWN_ARTIFACTS[RELIABILITY_BATTERY_REPORT](made.model_dump_json()) == made
    with pytest.raises(ValidationError):
        ReliabilityBatteryReport(**made.model_dump(), extra="rejected")
    with pytest.raises(ValidationError):
        report(entries=made.entries[:-1])
    with pytest.raises(ValidationError):
        entry(RELIABILITY_BATTERY_MEMBERS[0], observed="not ok", green=True)


def test_battery_derives_members_from_fault_process_clock_and_head_seams(tmp_path):
    process = HeadProcess("b" * 40)
    made = run(repo=Path("checkout"), evidence_root=tmp_path, clock=DeterministicClock(),
               fs=LocalFilesystem(), process=process, env={})
    assert made.produced_at_sha == "b" * 40
    assert [entry.observed for entry in made.entries] == [
        "failure=quota_exhausted;cooldown=2026-01-01T01:00:00+00:00",
        "first=quota_exhausted;second=quota_exhausted;all_cooling=quota_exhausted;recovered=codex",
        "failure=unclassified;calls=codex",
    ]
    assert all(entry.green for entry in made.entries)
    assert process.calls == [["git", "-C", "checkout", "rev-parse", "--verify", "HEAD"]]


def test_battery_returns_only_a_report_and_a_bad_member_journal_goes_red(tmp_path):
    process = HeadProcess()
    made = run(repo=Path("checkout"), evidence_root=tmp_path / "evidence",
               clock=DeterministicClock(), fs=LocalFilesystem(), process=process, env={})
    assert isinstance(made, ReliabilityBatteryReport)
    assert not list((tmp_path / "evidence").rglob(RELIABILITY_BATTERY_REPORT))
    broken = tmp_path / "broken" / "journal"
    broken.mkdir(parents=True)
    (broken / "000001.jsonl").write_text("not json\n")
    assert _auditor(broken.parent) == "red"
    empty = tmp_path / "empty" / "journal"
    empty.mkdir(parents=True)
    assert _auditor(empty.parent) == "red"


def test_quota_member_goes_red_when_the_boundary_did_not_arm_its_cooldown(tmp_path, monkeypatch):
    def missing_cooldown(self, provider):
        return self._clock()

    monkeypatch.setattr(ProviderRuntime, "cool_down", missing_cooldown)
    quota = asyncio.run(_member(
        member="classified_quota_exhaustion", root=tmp_path,
        clock=DeterministicClock(), fs=LocalFilesystem()))
    assert quota.observed.endswith("cooldown=missing")
    assert quota.auditor == "green" and not quota.green
