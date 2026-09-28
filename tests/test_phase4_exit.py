"""Phase 4 closes only from the committed provider reliability report."""

import asyncio
import hashlib
import os
from pathlib import Path

from squatch.artifacts import RELIABILITY_BATTERY_MEMBERS, ReliabilityBatteryReport
from squatch.git import Git
from squatch.seams import SubprocessExec


REPO = Path(__file__).resolve().parent.parent
REPORT = REPO / "tickets" / "reliability-run" / "reliability-battery-report.json"
CORE = ("retro-drain-invoker", "retro-box-activation", "phase5-continue")


def _git_blob_id(data):
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def test_committed_green_reliability_report_closes_phase4_before_core_read():
    data = REPORT.read_bytes()
    git = Git(SubprocessExec(), env=os.environ, timeout=30)
    committed = asyncio.run(git.rev_parse(
        REPO, "HEAD:tickets/reliability-run/reliability-battery-report.json"))
    assert _git_blob_id(data) == committed

    report = ReliabilityBatteryReport.model_validate_json(data)
    assert tuple(entry.member for entry in report.entries) == RELIABILITY_BATTERY_MEMBERS
    assert RELIABILITY_BATTERY_MEMBERS == (
        "classified_quota_exhaustion",
        "all_candidates_cooling_recovery",
        "unclassified_failure_preservation",
    )
    assert all(entry.observed == entry.expected for entry in report.entries)
    assert all(entry.auditor == "green" and entry.green is True
               for entry in report.entries)

    # Core contracts are inspected only after committed evidence has parsed green.
    for stem in CORE:
        assert (REPO / "tickets" / stem / "ticket.md").is_file()
