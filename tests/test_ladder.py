"""The capability rung walk and its journal folds."""

from squatch.config import Config
from squatch.journal import Event
from squatch.ladder import (IDENTICAL_TERMINALS, Rung, effective, identical,
                            next_rung, oscillating, pending_rung, rungs)
from squatch.providers import Registry
from squatch.tickets import Ticket

TS = "2026-09-25T12:00:00+00:00"


def event(type_, body, *, stem="work"):
    return Event(v=1, type=type_, ts=TS, ticket=stem, key=None, body=body)


def registry():
    config = Config.model_validate({
        "schema_version": 1, "state_dir": ".state",
        "providers": [{"name": "codex", "kind": "cli",
                       "models_by_tier": {"low": "a", "medium": "b",
                                          "high": "c", "max": "c"},
                       "limits": {"concurrency": 1, "est_cost_per_call_usd": 1}}],
        "routing": [{"tier": tier, "surface": "implement",
                     "candidates": [{"provider": "codex"}]}
                    for tier in ("low", "medium", "high", "max")]})
    return Registry(config)


def test_next_rung_walks_models_first_and_skips_a_same_model_tier():
    assert IDENTICAL_TERMINALS == 3
    first = next_rung(registry(), Rung("medium", "medium"))
    assert first == Rung("high", "medium")
    second = next_rung(registry(), first)
    assert second == Rung("high", "high")
    third = next_rung(registry(), second)
    assert third == Rung("high", "max")
    assert next_rung(registry(), third) is None


def test_rungs_folds_retry_draws_only_and_operator_keep_resets_it():
    rung = {"tier": "high", "effort": "max"}
    retry = event("cap_consumed", {"cap": "retry", "rung": rung})
    other = event("cap_consumed", {"cap": "infra",
                                    "rung": {"tier": "low", "effort": "low"}})
    machine = event("signal", {"kind": "confirm", "actor": "machine"})
    operator = event("signal", {"kind": "confirm", "actor": "operator"})
    assert rungs((retry, other), "work") == Rung("high", "max")
    assert rungs((retry, machine), "work") == Rung("high", "max")
    assert rungs((retry, operator), "work") is None


def test_pending_rung_is_bounded_by_an_operator_keep():
    routed = event("state_transition", {
        "to": "gate_failed", "routed": "ladder",
        "rung": {"tier": "high", "effort": "high"}})
    operator = event("signal", {"kind": "confirm", "actor": "operator"})
    assert pending_rung((routed,), "work") == Rung("high", "high")
    assert pending_rung((routed, operator), "work") is None


def test_effective_uses_authored_values_until_a_rung_exists():
    ticket = Ticket("work", "confirmed", "human", "P1", "feature", "medium", "low",
                    (), (), (), (), "goal", (), (), None, 1, 2, ())
    assert effective(ticket, None) == ("medium", "low")
    assert effective(ticket, Rung("high", "max")) == ("high", "max")


def terminal(reason, *, codes=("verification",), outcome="gate_failed", detail=None):
    body = {"to": outcome, "reason": reason, "finding_codes": list(codes)}
    if detail is not None:
        body["detail"] = detail
    return event("state_transition", body)


def test_identical_uses_code_reason_and_is_bounded_by_operator_keep():
    same = [terminal("verification", detail=detail)
            for detail in ("exception one", "exception two", "exception three")]
    assert identical(same, "work")
    assert not identical([*same[:2], terminal("scope_fence")], "work")
    keep = event("signal", {"kind": "confirm", "actor": "operator"})
    assert not identical([*same[:2], keep, same[2]], "work")


def test_oscillating_compares_the_last_three_finding_code_lists():
    a = terminal("a", codes=("verification",))
    b = terminal("b", codes=("scope_fence",))
    assert oscillating((a, b, a), "work")
    assert not oscillating((a, a, b), "work")


def test_repeat_detectors_restart_after_a_keep_or_ladder_climb():
    a = terminal("a", codes=("verification",))
    b = terminal("b", codes=("scope_fence",))
    keep = event("signal", {"kind": "confirm", "actor": "operator"})
    climb = event("state_transition", {
        "to": "gate_failed", "routed": "ladder", "reason": "a",
        "finding_codes": ["verification"],
        "rung": {"tier": "high", "effort": "medium"}})
    draw = event("cap_consumed", {
        "cap": "retry", "rung": {"tier": "high", "effort": "medium"}})

    assert not identical((a, a, climb, draw, a), "work")
    assert not oscillating((a, b, keep, a), "work")
    assert not oscillating((a, b, climb, draw, a), "work")
