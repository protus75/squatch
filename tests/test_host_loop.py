"""Closed schemas and production fixture-host evidence for the Phase 6 exit."""

import json

import pytest
from pydantic import ValidationError

from eval.host_loop import run
from squatch.artifacts import (EXIT_RECEIPT, HOST_LOOP_REPORT, ExitReceipt,
                               HostLoopReport)
from squatch.journal import read_events
from squatch.stages import KNOWN_ARTIFACTS


def entries():
    return (
        {"member": "machine_ticket_merge", "scenario": "one", "observable": "merged",
         "producing_run": "one/0"},
        {"member": "machine_ticket_merge", "scenario": "two", "observable": "merged",
         "producing_run": "two/0"},
        {"member": "machine_ticket_merge", "scenario": "three", "observable": "merged",
         "producing_run": "three/0"},
        {"member": "report_to_regression_bug_loop", "scenario": "report",
         "observable": "authored", "producing_run": "two/0"},
        {"member": "escape_attribution", "scenario": "escape",
         "observable": "trailer", "producing_run": "three/0"},
    )


def test_closed_artifacts_and_ordinary_lane_registration_refuse_unknown_fields():
    report = HostLoopReport(schema_version=1, produced_at_sha="fixture", entries=entries())
    receipt = ExitReceipt(schema_version=1, produced_at_sha="fixture",
                          host_loop_digest="abc", go_grade_verdict="NO_GO")
    assert KNOWN_ARTIFACTS[HOST_LOOP_REPORT](report.model_dump_json()) == report
    assert KNOWN_ARTIFACTS[EXIT_RECEIPT](receipt.model_dump_json()) == receipt
    for model, value in ((HostLoopReport, report), (ExitReceipt, receipt)):
        with pytest.raises(ValidationError) as exc:
            model.model_validate({**value.model_dump(), "unknown": True})
        assert any(error["type"] == "extra_forbidden" for error in exc.value.errors())


def test_report_requires_three_distinct_machine_runs_and_both_closed_loops():
    with pytest.raises(ValidationError, match="three distinct producing runs"):
        HostLoopReport(schema_version=1, produced_at_sha="fixture",
                       entries=entries()[:2] + entries()[3:])
    with pytest.raises(ValidationError, match="bug-loop and escape"):
        HostLoopReport(schema_version=1, produced_at_sha="fixture", entries=entries()[:3])


def test_real_serve_drives_machine_confirms_triage_bug_loop_and_escape_attribution(tmp_path):
    report = run(evidence_root=tmp_path)
    host = tmp_path / "fixture-host"
    state = host / ".squatch" / "state"
    events = tuple(read_events(state))
    merges = [entry for entry in report.entries if entry.member == "machine_ticket_merge"]

    assert len(merges) == len({entry.producing_run for entry in merges}) == 3
    assert {entry.scenario for entry in merges} == {
        "fixture-deterministic-app", "fixture-regression-fix", "fixture-machine-escape"}
    assert all("control/" in entry.observable and "supervised-release/" in entry.observable
               and "merged:" in entry.observable for entry in merges)
    assert any(event.body.get("kind") == "control_decision"
               and (event.body.get("request") or {}).get("action") == "confirm"
               and (event.body.get("request") or {}).get("actor") == "machine"
               and event.body.get("outcome") == "accepted" and event.body.get("applied")
               for event in events)

    regression, escape = report.entries[-2:]
    assert regression.member == "report_to_regression_bug_loop"
    assert "report-inbox->triage->fixture-regression-fix->merged" in regression.observable
    ticket = (host / "tickets/fixture-regression-fix/ticket.md").read_text()
    assert "kind: bug" in ticket and "## Regression" in ticket
    assert "evidence/" in ticket
    assert escape.member == "escape_attribution"
    assert "squatch-ticket=fixture-machine-escape" in escape.observable
    assert (host / ".squatch/report-inbox/regression.report.filed").is_file()
    assert (host / ".squatch/report-inbox/escape.report.filed").is_file()
    assert not list(tmp_path.rglob(HOST_LOOP_REPORT))
    assert not list(tmp_path.rglob(EXIT_RECEIPT))

    triage_effects = [event for event in events if event.type == "effect_completion"
                      and event.key and event.key.startswith("llm/triage/")]
    assert len(triage_effects) >= 2
    assert any(event.body.get("kind") == "triage_pass"
               and "fixture-regression-fix"
               in event.body.get("triaged", {}).get("authored", ()) for event in events)
    assert any(event.body.get("kind") == "triage_pass"
               and event.body.get("triaged", {}).get("tombstone") for event in events)

    # The report is returned to its caller. Construction never serializes either terminal file.
    json.dumps(report.model_dump(mode="json"))
