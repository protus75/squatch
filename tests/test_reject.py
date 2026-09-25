"""Deterministic Reject routing and the unresolved-arrival fold."""

import pytest

from squatch.config import Config
from squatch.diagnose import DiagnosisRecord
from squatch.journal import Event
from squatch.ladder import Rung
from squatch.reject import ARRIVAL, MARKER, awaiting, route

TS = "2026-09-25T12:00:00+00:00"


def event(type_, body, *, stem="work"):
    return Event(v=1, type=type_, ts=TS, ticket=stem, key=None, body=body)


def config(**caps):
    return Config.model_validate({
        "schema_version": 1, "state_dir": ".state",
        "providers": [{"name": "codex", "kind": "cli",
                       "models_by_tier": {"low": "a", "medium": "b",
                                          "high": "c", "max": "c"},
                       "limits": {"concurrency": 1, "est_cost_per_call_usd": 1}}],
        "routing": [{"tier": tier, "surface": "implement",
                     "candidates": [{"provider": "codex"}]}
                    for tier in ("low", "medium", "high", "max")],
        "caps": caps})


def record(*, call="ok", verdict="retry", outcome="gate_failed"):
    return DiagnosisRecord(run_seq=0, outcome=outcome, call=call, verdict=verdict,
                           lessons=(), reason="diagnosed" if verdict is not None else None,
                           detail=None)


@pytest.mark.parametrize("verdict,routed", [
    ("reject", MARKER), ("abandon-human", MARKER), ("split", MARKER),
    ("retry", None), ("escalate", "ladder"),
])
def test_route_dispatches_the_closed_verdict_vocabulary(verdict, routed):
    result = route(config(), (), "work", "gate_failed", record(verdict=verdict))
    assert result.routed == routed
    if routed:
        assert verdict in result.reason


def test_escalate_walks_a_rung_and_exhaustion_routes_to_reject():
    climbed = route(config(), (), "work", "gate_failed", record(verdict="escalate"),
                    current=Rung("medium", "medium"))
    assert climbed == type(climbed)("ladder", "diagnosis verdict escalate",
                                    Rung("high", "medium"))
    exhausted = route(config(), (), "work", "gate_failed", record(verdict="escalate"),
                      current=Rung("high", "max"))
    assert exhausted.routed == MARKER and "ladder exhausted" in exhausted.reason


def test_retry_same_wall_climbs_but_a_cleared_wall_has_no_marker():
    prior = event("state_transition", {"to": "gate_failed", "reason": "verification",
                                        "finding_codes": ["verification"]})
    draw = event("cap_consumed", {"cap": "retry"})

    class Delivery:
        outcome = "gate_failed"
        findings = ()

    from squatch.artifacts import Finding
    same = Delivery()
    same.findings = [Finding(code="verification", message="different detail",
                             paved_road="fix it")]
    climbed = route(config(), (prior, draw), "work", "gate_failed", record(),
                    current=Rung("medium", "medium"), delivery=same)
    assert climbed.routed == "ladder" and climbed.rung == Rung("high", "medium")

    cleared = Delivery()
    cleared.findings = [Finding(code="scope_fence", message="new wall", paved_road="fix it")]
    assert route(config(), (prior, draw), "work", "gate_failed", record(),
                 current=Rung("medium", "medium"), delivery=cleared).routed is None


def test_spent_cap_precedes_an_escalate_ladder_arm():
    draw = event("cap_consumed", {"cap": "retry"})
    routed = route(config(retry=1), (draw,), "work", "gate_failed",
                   record(verdict="escalate"), current=Rung("medium", "medium"))
    assert routed.routed == MARKER and routed.reason.startswith("retry cap spent")


def test_route_prioritizes_spent_caps_then_skip_and_null_verdict_rules():
    draw = event("cap_consumed", {"cap": "diagnosis"})
    result = route(config(diagnosis=1, retry=1), (draw,), "work", "gate_failed",
                   record(verdict="retry"))
    assert result.routed == MARKER
    assert result.reason == "diagnosis cap spent (1 of 1 drawn)"

    skipped = route(config(), (), "work", "premise_failed",
                    record(call="skipped", verdict=None, outcome="premise_failed"))
    assert skipped.routed is None
    invalid = route(config(), (), "work", "gate_failed",
                    record(call="invalid_artifact", verdict=None))
    assert invalid == type(invalid)(MARKER, "no schema-valid diagnosis verdict")


def test_awaiting_accepts_a_marker_or_later_arrival_and_either_verdict_actor_releases():
    marked = event("state_transition", {"to": "gate_failed", "run_seq": 0,
                                         "routed": MARKER, "reject_reason": "reject"})
    assert awaiting((marked,))["work"].reason == "reject"

    terminal = event("state_transition", {"to": "gate_failed", "run_seq": 0})
    arrival = event("signal", {"kind": "escalation", "escalation": ARRIVAL,
                                "reason": "legacy spent", "run_seq": 0})
    assert awaiting((terminal, arrival))["work"].reason == "legacy spent"
    for kind, actor in (("confirm", "operator"), ("confirm", "machine"),
                        ("reject", "operator")):
        verdict = event("signal", {"kind": kind, "actor": actor})
        assert awaiting((terminal, arrival, verdict)) == {}
