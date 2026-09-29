from pathlib import Path

import pytest

from squatch.baseline import ABSENT, GO, NO_GO, REVOKED, BaselineResolution, resolve_baseline
from squatch.config import parse
from squatch.journal import Event
from squatch.providers import Registry


def config(*, model="m", auth=None, routing=True):
    provider = {"name": "codex", "kind": "cli", "models_by_tier": {
        "low": "l", "medium": model, "high": "h", "max": "x"},
        "limits": {"concurrency": 1, "est_cost_per_call_usd": 1}}
    if auth is not None:
        provider["auth"] = auth
    return parse({"schema_version": 1, "state_dir": ".state", "providers": [provider],
                  "routing": ([{"tier": "medium", "surface": "review",
                                "candidates": [{"provider": "codex"}]}] if routing else [])}, source="test")


def specs(tmp_path: Path, *, review_version="1.0", author_version="1.0") -> Path:
    target = tmp_path / "specs"
    target.mkdir()
    source = Path(__file__).parents[1] / "specs"
    for name, version in (("review", review_version), ("author", author_version)):
        text = (source / f"{name}.md").read_text()
        target.joinpath(f"{name}.md").write_text(
            text.replace('version: "1.0"', f'version: "{version}"', 1))
    return target


def event(body):
    return Event(1, "signal", "2026-01-01T00:00:00+00:00", None, None, body)


def go(cfg, *, tiers=("medium",), **changes):
    registry = Registry(cfg)
    identity = {surface: {tier: {"provider": registry.resolve(tier, surface).provider.name,
                                 "model": registry.resolve(tier, surface).model}
                          for tier in tiers}
                for surface in ("review", "author")}
    body = {"kind": "review_baseline", "verdict": "GO", "tiers": tiers,
            "identity": identity, "spec_major": {"review": 1, "author": 1}}
    body.update(changes)
    return event(body)


def test_closed_precedence_and_only_go_binds(tmp_path):
    cfg, directory = config(), specs(tmp_path)
    assert resolve_baseline(cfg, (), specs_dir=directory) == BaselineResolution(ABSENT, False)
    no_go = event({"kind": "review_baseline", "verdict": "NO_GO"})
    assert resolve_baseline(cfg, (go(cfg), no_go), specs_dir=directory) == BaselineResolution(NO_GO, False)
    assert resolve_baseline(cfg, (no_go, go(cfg)), specs_dir=directory) == BaselineResolution(GO, True)


def test_registry_and_spec_identity_are_explicit(tmp_path):
    cfg, directory = config(), specs(tmp_path)
    assert resolve_baseline(cfg, (go(cfg),), specs_dir=directory).binds
    changed = go(cfg, identity={"review": {"medium": {"provider": "codex", "model": "other"}},
                                "author": {"medium": {"provider": "codex", "model": "m"}}})
    assert resolve_baseline(cfg, (changed,), specs_dir=directory).state == REVOKED
    assert resolve_baseline(cfg, (go(cfg, spec_major={"review": 2, "author": 1}),),
                            specs_dir=directory).state == REVOKED


@pytest.mark.parametrize("body", [
    {"tiers": (), "identity": {}, "spec_major": {}},
    {"tiers": ("unknown",), "identity": {}, "spec_major": {}},
    {"tiers": ("medium",), "identity": [], "spec_major": {"review": 1, "author": 1}},
    {"tiers": ("medium",), "identity": {}, "spec_major": "1"},
    {"tiers": ("medium",), "identity": {}, "spec_major": {"review": "1", "author": 1}},
    {"tiers": ("medium",), "identity": {}, "spec_major": {"review": True, "author": True}},
])
def test_malformed_baseline_fields_revoke(tmp_path, body):
    cfg = config()
    baseline = go(cfg)
    changed = dict(baseline.body)
    changed.update(body)
    assert resolve_baseline(cfg, (event(changed),), specs_dir=specs(tmp_path)).state == REVOKED


@pytest.mark.parametrize("kwargs", [{"model": "OPERATOR-SETS-THIS"}, {"routing": False}])
def test_unresolved_routing_or_placeholders_revoke(tmp_path, kwargs):
    cfg = config(**kwargs)
    body = go(config()).body
    assert resolve_baseline(cfg, (event(body),), specs_dir=specs(tmp_path)).state == REVOKED


def test_placeholder_auth_revoke(tmp_path):
    cfg = config()
    cfg.providers[0].auth = "OPERATOR-SETS-THIS"
    assert resolve_baseline(cfg, (go(config()),), specs_dir=specs(tmp_path)).state == REVOKED


def test_unreadable_or_malformed_specs_revoke(tmp_path):
    cfg = config()
    assert resolve_baseline(cfg, (go(cfg),), specs_dir=tmp_path / "missing").state == REVOKED
    assert resolve_baseline(cfg, (go(cfg),), specs_dir=specs(tmp_path, review_version="1")).state == REVOKED


def test_torn_tail_preserves_selected_non_go_or_absence_and_revokes_go(tmp_path):
    cfg, directory = config(), specs(tmp_path)
    def torn_after(*events):
        yield from events
        raise OSError("torn tail")
    no_go = event({"kind": "review_baseline", "verdict": "NO_GO"})
    assert resolve_baseline(cfg, torn_after(), specs_dir=directory).state == ABSENT
    assert resolve_baseline(cfg, torn_after(no_go), specs_dir=directory).state == NO_GO
    assert resolve_baseline(cfg, torn_after(go(cfg)), specs_dir=directory).state == REVOKED
