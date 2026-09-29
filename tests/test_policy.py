import inspect

import pytest

import squatch.policy as policy
from squatch.config import parse
from squatch.policy import starting_state


def config(*, inventory=("specs/",)):
    return parse({
        "schema_version": 1, "state_dir": ".state",
        "providers": [{"name": "codex", "kind": "cli",
                       "models_by_tier": {"low": "l", "medium": "m", "high": "h", "max": "x"},
                       "limits": {"concurrency": 1, "est_cost_per_call_usd": 1}}],
        "routing": [{"tier": tier, "surface": "review", "candidates": [{"provider": "codex"}]}
                    for tier in ("low", "medium", "high", "max")],
        "engine_plane_safety_inventory": list(inventory),
    }, source="test")


def test_policy_owns_starting_state_but_not_baseline_reader():
    assert not hasattr(policy, "go_binds")
    assert "go_binds" in inspect.signature(starting_state).parameters


def test_without_go_every_policy_row_is_draft():
    cfg = config()
    for message_class in ("failure_report", "retro_finding", "override_report", "suggestion"):
        assert starting_state(cfg, message_class=message_class, fence=(), reopened=False,
                              go_binds=False) == "draft"
    for origin, repro in (("self_diagnosed", False), ("player", True), ("player", False)):
        assert starting_state(cfg, message_class="bug_report", bug_origin=origin,
                              has_repro=repro, fence=(), reopened=False,
                              go_binds=False) == "draft"


def test_starting_state_policy_and_authority_overrides():
    cfg = config()
    assert starting_state(cfg, message_class="failure_report", fence=("src/",), reopened=False,
                          go_binds=True) == "confirmed"
    assert starting_state(cfg, message_class="suggestion", fence=("src/",), reopened=False,
                          go_binds=True) == "draft"
    assert starting_state(cfg, message_class="failure_report", fence=("specs/review.md",),
                          reopened=False, go_binds=True) == "draft"
    assert starting_state(config(inventory=()), message_class="failure_report", fence=("src/",),
                          reopened=False, go_binds=True) == "draft"
    assert starting_state(cfg, message_class="failure_report", fence=("src/",), reopened=True,
                          go_binds=True) == "draft"
    assert starting_state(cfg, message_class="failure_report", fence=("src/",), reopened=False,
                          go_binds=False) == "draft"


def test_bug_origin_is_closed():
    with pytest.raises(ValueError, match="bug_origin"):
        starting_state(config(), message_class="bug_report", bug_origin="robot",
                       has_repro=True, go_binds=True)


@pytest.mark.parametrize("message_class,origin,repro", [
    ("failure_report", None, False),
    ("retro_finding", None, False),
    ("override_report", None, False),
    ("suggestion", None, False),
    ("bug_report", "self_diagnosed", False),
    ("bug_report", "player", True),
    ("bug_report", "player", False),
])
def test_bypass_forces_every_policy_row_to_draft(message_class, origin, repro):
    assert starting_state(
        config(), message_class=message_class, bug_origin=origin, has_repro=repro,
        fence=("src/",), reopened=False, bypass=True, go_binds=True) == "draft"
