import copy
from datetime import datetime, timezone

import pytest

from squatch.config import parse
from squatch.journal import Journal
from eval.harness import baselined_identity, spec_major, spec_versions
from squatch.providers import Registry
from squatch.policy import go_binds, starting_state


def config(*, inventory=("specs/",)):
    return parse({
        "schema_version": 1, "state_dir": ".state",
        "providers": [{"name": "codex", "kind": "cli",
                       "models_by_tier": {"low": "l", "medium": "m", "high": "h", "max": "x"},
                       "limits": {"concurrency": 1, "est_cost_per_call_usd": 1}}],
        "routing": [{"tier": tier, "surface": "review",
                     "candidates": [{"provider": "codex"}]}
                    for tier in ("low", "medium", "high", "max")],
        "engine_plane_safety_inventory": list(inventory),
    }, source="test")


def test_without_go_every_policy_row_is_draft():
    cfg = config()
    assert not go_binds(cfg, ())
    for message_class in ("failure_report", "retro_finding", "override_report", "suggestion"):
        assert starting_state(cfg, message_class=message_class, fence=(), reopened=False,
                              go_binds=False) == "draft"
    for origin, repro in (("self_diagnosed", False), ("player", True), ("player", False)):
        assert starting_state(cfg, message_class="bug_report", bug_origin=origin,
                              has_repro=repro, fence=(), reopened=False,
                              go_binds=False) == "draft"


def test_binding_go_identity_and_overrides(tmp_path):
    cfg = config()
    tiers = ("high",)
    identity = baselined_identity(Registry(cfg), tiers)
    majors = {surface: spec_major(version)
              for surface, version in spec_versions().items()}
    with Journal(tmp_path, clock=lambda: __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc)) as journal:
        journal.append("signal", {"kind": "review_baseline", "verdict": "GO",
                                  "tiers": tiers, "identity": {
                                      surface: {tier: row.model_dump(mode="json")
                                                for tier, row in rows.items()}
                                      for surface, rows in identity.items()},
                                  "spec_major": majors})
        events = tuple(journal.read())
    assert go_binds(cfg, events)
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

    drifted = copy.deepcopy(events[-1].body)
    drifted["identity"]["review"]["high"]["model"] = "changed"
    with Journal(tmp_path / "drift", clock=lambda: datetime.now(timezone.utc)) as journal:
        journal.append("signal", drifted)
        assert not go_binds(cfg, tuple(journal.read()))


@pytest.mark.parametrize("tiers", [None, (), ("unknown",)])
def test_go_without_valid_exercised_tiers_fails_closed(tmp_path, tiers):
    cfg = config()
    body = {"kind": "review_baseline", "verdict": "GO", "identity": {},
            "spec_major": {}}
    if tiers is not None:
        body["tiers"] = tiers
    with Journal(tmp_path, clock=lambda: datetime.now(timezone.utc)) as journal:
        journal.append("signal", body)
        assert not go_binds(cfg, tuple(journal.read()))


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
