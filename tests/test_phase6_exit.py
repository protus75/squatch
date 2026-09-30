"""Terminal Phase 6 evidence and receipt closure."""

import ast
import asyncio
import hashlib
import json
import os
import re
from pathlib import Path

import pytest

import eval.host_loop as host_loop
from squatch.artifacts import (EXIT_RECEIPT, HOST_LOOP_REPORT, REVIEW_BASELINE_REPORT,
                               ExitReceipt, HostLoopReport, ReviewBaselineReport)
from squatch.git import Git
from squatch.seams import SubprocessExec
from squatch.stages import KNOWN_ARTIFACTS


REPO = Path(__file__).resolve().parent.parent
OUTBOX = REPO / "tickets" / "phase6-exit"
HOST_REPORT = OUTBOX / HOST_LOOP_REPORT
RECEIPT = OUTBOX / EXIT_RECEIPT
GO_GRADE = REPO / "tickets" / "go-grade-run" / REVIEW_BASELINE_REPORT
MEMBERS = (
    "machine_ticket_merge",
    "machine_ticket_merge",
    "machine_ticket_merge",
    "report_to_regression_bug_loop",
    "escape_attribution",
)
FENCE = (
    "tickets/phase6-exit/host-loop-report.json",
    "tickets/phase6-exit/exit-receipt.json",
    "tests/test_phase6_exit.py",
)


def _blob_id(data):
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def _committed_grade():
    data = GO_GRADE.read_bytes()
    git = Git(SubprocessExec(), env=os.environ, timeout=30)
    committed = asyncio.run(git.rev_parse(
        REPO, f"HEAD:tickets/go-grade-run/{REVIEW_BASELINE_REPORT}"))
    assert _blob_id(data) == committed
    return ReviewBaselineReport.model_validate_json(data)


def _grade_verdict(report, signals):
    summary = report.scored_summary
    if summary.known_bad + summary.clean < report.planted_defect_count:
        return "NO_GO"

    current = [signal for signal in signals
               if signal.get("kind") == "review_baseline"
               and signal.get("produced_at_sha") == report.produced_at_sha]
    if not current:
        raise ValueError("complete report requires a current-build review_baseline signal")
    signal = current[-1]
    expected = report.verdict_signal_identity.model_dump(mode="json")
    observed = {key: signal.get(key) for key in ("tiers", "identity", "spec_major")}
    if observed != expected:
        raise ValueError("complete report verdict identity does not match")
    try:
        return {"GO": "GO", "NO-GO": "NO_GO"}[signal.get("verdict")]
    except KeyError as exc:
        raise ValueError("complete report has an invalid verdict") from exc


def _complete(report):
    body = report.model_dump(mode="json")
    body["scored_summary"]["known_bad"] = report.planted_defect_count
    body["scored_summary"]["clean"] = 0
    return ReviewBaselineReport.model_validate(body)


def _signal(report, verdict="GO"):
    return {
        "kind": "review_baseline",
        "verdict": verdict,
        "produced_at_sha": report.produced_at_sha,
        **report.verdict_signal_identity.model_dump(mode="json"),
    }


def _ticket_fence():
    lines = (OUTBOX / "ticket.md").read_text().splitlines()
    start = lines.index("## Scope fence") + 1
    end = next(index for index in range(start, len(lines))
               if lines[index].startswith("## "))
    return tuple(line.removeprefix("- ") for line in lines[start:end] if line)


def _registered_identity(report):
    return tuple((entry.member, entry.scenario, entry.producing_run.split("/", 1)[0])
                 for entry in report.entries)


def _assert_registered_evidence(report, registered):
    assert _registered_identity(report) == _registered_identity(registered)


@pytest.fixture(scope="module")
def registered_report(tmp_path_factory):
    evidence_root = tmp_path_factory.mktemp("registered-host-loop")
    report = host_loop.run(evidence_root=evidence_root)
    assert not list(evidence_root.rglob(HOST_LOOP_REPORT))
    assert not list(evidence_root.rglob(EXIT_RECEIPT))
    return report


def test_registered_producer_returns_closed_fixture_host_report(registered_report):
    assert host_loop.FIXTURE == REPO / "hosts" / "fixture"
    assert isinstance(registered_report, HostLoopReport)
    assert KNOWN_ARTIFACTS[HOST_LOOP_REPORT](
        registered_report.model_dump_json()) == registered_report
    assert tuple(entry.member for entry in registered_report.entries) == MEMBERS
    assert len({entry.producing_run for entry in registered_report.entries[:3]}) == 3


def test_exit_serialized_registered_artifacts_and_exact_digest(registered_report):
    report_bytes = HOST_REPORT.read_bytes()
    receipt_bytes = RECEIPT.read_bytes()
    report = KNOWN_ARTIFACTS[HOST_LOOP_REPORT](report_bytes)
    receipt = KNOWN_ARTIFACTS[EXIT_RECEIPT](receipt_bytes)

    assert isinstance(report, HostLoopReport)
    assert isinstance(receipt, ExitReceipt)
    _assert_registered_evidence(report, registered_report)
    assert tuple(entry.member for entry in report.entries) == MEMBERS
    assert len({entry.producing_run for entry in report.entries[:3]}) == 3
    assert receipt.produced_at_sha == report.produced_at_sha
    assert receipt.host_loop_digest == hashlib.sha256(report_bytes).hexdigest()
    assert re.fullmatch(r"[0-9a-f]{64}", receipt.host_loop_digest)
    assert receipt.go_grade_verdict == "NO_GO"
    assert report_bytes == (json.dumps(report.model_dump(mode="json"),
                                       sort_keys=True, indent=2) + "\n").encode()
    assert receipt_bytes == (json.dumps(receipt.model_dump(mode="json"),
                                        sort_keys=True, indent=2) + "\n").encode()


def test_unregistered_or_live_host_evidence_is_rejected(registered_report):
    for field, value in (("scenario", "unregistered-live-host"),
                         ("producing_run", "unregistered-live-host/10")):
        body = registered_report.model_dump(mode="json")
        body["entries"][0][field] = value
        fabricated = HostLoopReport.model_validate(body)
        with pytest.raises(AssertionError):
            _assert_registered_evidence(fabricated, registered_report)


def test_incomplete_committed_grade_is_no_go_without_signal_read():
    report = _committed_grade()
    assert report.scored_summary.known_bad + report.scored_summary.clean == 41
    assert report.planted_defect_count == 50

    class RefuseRead:
        def __iter__(self):
            raise AssertionError("incomplete grade must not read signals")

    assert _grade_verdict(report, RefuseRead()) == "NO_GO"


def test_complete_grade_requires_latest_current_build_identity_and_maps_verdicts():
    report = _complete(_committed_grade())
    assert _grade_verdict(report, (_signal(report, "GO"),)) == "GO"
    assert _grade_verdict(report, (_signal(report, "NO-GO"),)) == "NO_GO"

    with pytest.raises(ValueError, match="current-build"):
        _grade_verdict(report, ())
    wrong_build = _signal(report)
    wrong_build["produced_at_sha"] = "other-build"
    with pytest.raises(ValueError, match="current-build"):
        _grade_verdict(report, (wrong_build,))
    wrong_identity = _signal(report)
    wrong_identity["spec_major"] = {"author": 2, "review": 1}
    with pytest.raises(ValueError, match="identity"):
        _grade_verdict(report, (_signal(report), wrong_identity))


def test_terminal_fence_has_no_engine_edit_successor_or_external_evidence_input():
    assert _ticket_fence() == FENCE
    assert not (REPO / "tickets" / "phase6-continue-09").exists()
    continuation = (REPO / "tickets" / "phase6-continue-08" / "ticket.md").read_text()
    assert "The terminal row contains `phase6-exit` alone, has no successor" in continuation

    source = Path(__file__).read_text()
    tree = ast.parse(source)
    imports = {(node.module, alias.name) for node in ast.walk(tree)
               if isinstance(node, ast.ImportFrom) for alias in node.names}
    calls = {node.func.id for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert not any(module == "squatch.journal" for module, _name in imports)
    assert calls.isdisjoint({"Journal", "read_events"})
    assert ".squatch/" + "state" not in source

    git = Git(SubprocessExec(), env=os.environ, timeout=30)
    adding_commit = asyncio.run(git._run(
        REPO, "log", "--diff-filter=A", "--format=%H", "--", "tests/test_phase6_exit.py"))
    commits = tuple(line for line in adding_commit.splitlines() if line)
    assert len(commits) == 1
    changed = asyncio.run(git._run(
        REPO, "diff-tree", "--no-commit-id", "--name-only", "-r", commits[0]))
    assert tuple(line for line in changed.splitlines() if line) == ("tests/test_phase6_exit.py",)
