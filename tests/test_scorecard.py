"""The pure Phase 5 surface-scorecard projection."""

import builtins
import pathlib
import subprocess
from datetime import datetime, timezone

from squatch.journal import Event
from squatch.retro import ORIGIN_BOUNDARY, RetroArtifact, Window, render_report as render_retro
from squatch.scorecard import project_scorecard, render_report

T0 = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)


def event(*, key, result, ticket="ticket"):
    return Event(
        v=1, type="effect_completion", ts=T0.isoformat(), ticket=ticket, key=key,
        body={"result": result})


def window(events):
    return Window(tuple(events), T0).projection(sha="0123abcd", spec_version="1.0")


def invoice(*checks):
    return {"invoice": {"checks": list(checks)}}


def check(code, verdict="pass", bypassed=False):
    return {"code": code, "verdict": verdict, "bypassed": bypassed}


def test_window_folds_only_well_formed_completed_check_invoices_in_tuple_order():
    projection = window((
        event(key="check/zeta/1", result=invoice(check("review", "fail"))),
        event(key="check/alpha/0", result=invoice(check("scope", bypassed=True), check("review"))),
        event(key="check/bad/0", result={"invoice": {"checks": [{"code": "bad"}]}}),
        event(key="check/no-invoice/0", result={}),
        event(key="check/wrong/key/0", result=invoice(check("bad"))),
    ))

    assert projection.check_observations == (
        ("zeta", "review", "fail", False),
        ("alpha", "scope", "pass", True),
        ("alpha", "review", "pass", False),
    )


def test_scorecard_counts_distinct_tickets_catches_bypasses_and_phase_five_escapes():
    scorecard = project_scorecard(window((
        event(key="check/a/0", result=invoice(check("verify", "fail"), check("verify", "fail", True))),
        event(key="check/a/1", result=invoice(check("verify"))),
        event(key="check/b/0", result=invoice(check("verify", "fail"))),
    )))

    [row] = scorecard.surfaces
    assert scorecard.boundary == ORIGIN_BOUNDARY
    assert scorecard.merged_ticket_count == 0
    assert scorecard.spend_usd == 0 and scorecard.tokens == 0
    assert scorecard.gate_failure_count == 0
    assert (row.surface, row.evaluated_tickets, row.catches, row.bypass_count) == (
        "verify", 2, 2, 1)
    assert row.catch_rate == 0.5
    assert (row.escapes, row.escape_rate, row.prune_candidate) == (0, 0, False)


def test_zero_denominator_and_twenty_five_ticket_prune_threshold():
    assert project_scorecard(window(())).surfaces == ()

    below_threshold = [event(key=f"check/below-{number}/0", result=invoice(check("quiet")))
                       for number in range(24)]
    at_threshold = [event(key=f"check/at-{number}/0", result=invoice(check("prunable")))
                    for number in range(25)]
    caught = [event(key=f"check/caught-{number}/0", result=invoice(
        check("caught", "fail" if number == 0 else "pass"))) for number in range(25)]
    rows = {row.surface: row for row in project_scorecard(
        window(below_threshold + at_threshold + caught)).surfaces}

    assert (rows["quiet"].catch_rate, rows["quiet"].escape_rate,
            rows["quiet"].prune_candidate) == (0, 0, False)
    assert (rows["prunable"].catch_rate, rows["prunable"].escape_rate,
            rows["prunable"].prune_candidate) == (0, 0, True)
    assert rows["caught"].prune_candidate is False


def test_scorecard_sorting_rendering_and_projection_are_deterministic_and_pure(monkeypatch):
    projection = window((
        event(key="check/one/0", result=invoice(check("zeta"), check("alpha", "fail"))),
    ))
    before = projection.model_dump()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("scorecard projection must have no effects")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(pathlib.Path, "open", forbidden)
    monkeypatch.setattr(pathlib.Path, "write_text", forbidden)
    monkeypatch.setattr(pathlib.Path, "write_bytes", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    scorecard = project_scorecard(projection)

    assert tuple(row.surface for row in scorecard.surfaces) == ("alpha", "zeta")
    assert projection.model_dump() == before
    assert render_report(scorecard) == (
        "## Surface scorecard\n\n"
        "| Surface | Evaluated tickets | Catches | Escapes | Bypasses | Catch rate | Escape rate | Prune candidate |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |\n"
        "| `alpha` | 1 | 1 | 0 | 0 | 1.000000 | 0.000000 | no |\n"
        "| `zeta` | 1 | 0 | 0 | 0 | 0.000000 | 0.000000 | no |\n")
    report = render_retro(
        "000001", "quiescence", projection,
        RetroArtifact(summary="Healthy.", produced_by_spec_version="1.0",
                      produced_at_sha="0123abcd"))
    assert "## Surface scorecard\n\n" in report
