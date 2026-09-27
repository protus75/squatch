"""Phase 3 closes only from the committed deterministic soak report."""

import asyncio
import hashlib
import os
from pathlib import Path

from squatch.artifacts import DAEMON_SOAK_MEMBERS, DaemonSoakReport
from squatch.git import Git
from squatch.seams import SubprocessExec


REPO = Path(__file__).resolve().parent.parent
REPORT = REPO / "tickets" / "soak-run" / "daemon-soak-report.json"
EXPECTED = {
    "worker_killed_mid_run": (
        "kill a production-dispatched worker while its provider process is active",
        "the recovery alert, abandoned run, and clean re-dispatched terminal",
        "recovery_alert:abandoned->merged;redispatched=1",
        "alert",
    ),
    "conflict_resolution_rungs": (
        "plant two real Git conflicts, one union-resolvable and one unresolved",
        "the production conflict facts while main stays at its green pre-admission tree",
        "mechanical->rework;main=green",
        "alert",
    ),
    "semantic_conflict_integration_red": (
        "fail the real post-rebase integration command through the process seam",
        "the production integration-red terminal while main stays green and unchanged",
        "integration_red:verification;main=green",
        "box",
    ),
}


def _git_blob_id(data):
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def test_committed_soak_report_closes_phase3_without_running_the_soak():
    data = REPORT.read_bytes()
    git = Git(SubprocessExec(), env=os.environ, timeout=30)
    committed = asyncio.run(git.rev_parse(REPO, "HEAD:tickets/soak-run/daemon-soak-report.json"))
    assert _git_blob_id(data) == committed

    report = DaemonSoakReport.model_validate_json(data)
    assert report.injected_hours >= 24
    assert tuple(entry.member for entry in report.entries) == DAEMON_SOAK_MEMBERS
    assert tuple(EXPECTED) == DAEMON_SOAK_MEMBERS

    for entry in report.entries:
        fault, observable, expected, disposition = EXPECTED[entry.member]
        assert (entry.fault, entry.observable, entry.expected, entry.disposition) == (
            fault, observable, expected, disposition)
        assert entry.producing_run
        assert entry.observed == entry.expected
        assert entry.auditor == "green"
        assert entry.green is True
