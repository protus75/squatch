"""config.py: the host config loader (SQUATCH_PLAN.md section 15).

One `config.yaml`, PyYAML `safe_load`, validated fail-closed against the
section 15 top-level schema behind the `schema_version` handshake. Every
refusal is a `ConfigError` naming the offending key by dotted path.
"""

import copy
from pathlib import Path

import pytest
import yaml

from squatch.config import SCHEMA_VERSION, Config, ConfigError, load, parse

VALID = {
    "schema_version": 1,
    "state_dir": "/tmp/squatch-state",
    "providers": [
        {
            "name": "claude",
            "kind": "cli",
            "auth": "ANTHROPIC_API_KEY",
            "models_by_tier": {"low": "haiku", "medium": "sonnet",
                               "high": "opus", "max": "opus"},
            "limits": {"concurrency": 1, "est_cost_per_call_usd": 1.0},
        },
        {
            "name": "codex",
            "kind": "cli",
            "models_by_tier": {"low": "mini", "medium": "mini",
                               "high": "codex", "max": "codex"},
            "limits": {"concurrency": 2, "quota_window_minutes": 30},
        },
    ],
    "routing": [
        {"tier": "medium", "surface": "implement",
         "candidates": [{"provider": "claude", "model": "sonnet"},
                        {"provider": "codex"}]},
    ],
    "review": {
        "mechanical": [{"code": "LINT", "argv": ["ruff", "check", "."],
                        "trigger": "always", "severity": "hard"}],
        "surfaces": [{"name": "arch", "trigger": ["squatch/"],
                      "rules_doc": "docs/arch.md", "severity": "soft"}],
        "trigger_map": {"squatch/": ["SCHEMA"]},
        "gate_severity": {"SCHEMA": "hard"},
    },
    "merge": {
        "safety_checks": ["LINT"],
        "strategies": [
            {"paths": ["README.md"], "strategy": "regenerate",
             "argv": ["python", "gen.py"]},
            {"paths": ["tickets/"], "strategy": "union"},
        ],
    },
    "scheduler": {"max_unmerged": 3},
    "notify": ["notify-send", "squatch"],
    "context_files": ["CLAUDE.md"],
}


def write(tmp_path: Path, data, name="config.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data) if not isinstance(data, str) else data)
    return path


def refused(data, source="config.yaml") -> ConfigError:
    with pytest.raises(ConfigError) as info:
        parse(data, source=source)
    return info.value


def variant(**overrides):
    data = copy.deepcopy(VALID)
    data.update(overrides)
    return data


# --- valid config -------------------------------------------------------------

def test_valid_config_parses_to_typed_values():
    cfg = parse(VALID, source="config.yaml")
    assert isinstance(cfg, Config)
    assert cfg.schema_version == SCHEMA_VERSION == 1
    assert cfg.state_dir == Path("/tmp/squatch-state")
    assert [p.name for p in cfg.providers] == ["claude", "codex"]
    assert cfg.providers[0].auth == "ANTHROPIC_API_KEY"
    assert cfg.providers[1].auth is None
    assert cfg.providers[0].models_by_tier.high == "opus"
    assert cfg.providers[0].limits.est_cost_per_call_usd == 1.0
    assert cfg.routing[0].candidates[1].model is None
    assert cfg.review.mechanical[0].argv == ["ruff", "check", "."]
    assert cfg.review.surfaces[0].trigger == ["squatch/"]
    assert cfg.merge.strategies[1].strategy == "union"
    assert cfg.scheduler.max_unmerged == 3
    assert cfg.notify == ["notify-send", "squatch"]
    assert cfg.context_files == [Path("CLAUDE.md")]


def test_absent_keys_take_the_shipped_defaults():
    cfg = parse(VALID, source="config.yaml")
    assert cfg.worktree_root == Path("/tmp/squatch-state/worktrees")
    assert cfg.providers[0].limits.quota_window_minutes == 60
    assert cfg.providers[1].limits.est_cost_per_call_usd is None
    assert cfg.routing_default_tier == "medium"
    assert cfg.caps.model_dump() == {"diagnosis": 6, "retry": 6, "premise_bounce": 2,
                                     "infra": 6, "quarantine": 5, "poison": 2}
    assert cfg.seeding.max_seeds_per_admission == 3
    assert cfg.circuit_breaker.k == 3
    assert cfg.circuit_breaker.cooldown_minutes == 10
    assert cfg.drain.max_runtime_hours == 12
    assert cfg.drain.max_ticket_minutes == 90
    assert cfg.engine_plane_safety_inventory == []
    assert cfg.box_policy.model_dump() == {
        "failure_report": "confirmed", "retro_finding": "confirmed",
        "override_report": "draft", "suggestion": "draft",
        "bug_report_self_diagnosed": "confirmed",
        "bug_report_player_repro": "confirmed",
        "bug_report_player_no_repro": "draft",
    }
    assert cfg.report_inbox is None


def test_minimal_config_needs_only_the_required_keys():
    cfg = parse({"schema_version": 1, "state_dir": "s", "providers": [],
                 "routing": []}, source="config.yaml")
    assert cfg.review.mechanical == [] and cfg.merge.strategies == []
    assert cfg.notify is None


def test_explicit_worktree_root_is_kept():
    cfg = parse(variant(worktree_root="/elsewhere"), source="config.yaml")
    assert cfg.worktree_root == Path("/elsewhere")


# --- locating the file ----------------------------------------------------------

def test_load_reads_config_yaml_at_the_cwd_by_default(tmp_path):
    write(tmp_path, VALID)
    cfg = load(cwd=tmp_path)
    assert cfg.state_dir == Path("/tmp/squatch-state")


def test_load_honours_an_explicit_config_path(tmp_path):
    path = write(tmp_path, VALID, name="other.yaml")
    assert load(path, cwd=tmp_path / "nowhere").state_dir == Path("/tmp/squatch-state")


def test_load_refuses_a_missing_file_naming_it(tmp_path):
    with pytest.raises(ConfigError, match="nope.yaml"):
        load(tmp_path / "nope.yaml", cwd=tmp_path)


def test_load_refuses_unparseable_yaml_naming_the_file(tmp_path):
    path = write(tmp_path, "schema_version: [1, 2")
    with pytest.raises(ConfigError, match="config.yaml"):
        load(path, cwd=tmp_path)


def test_load_errors_carry_the_source_path(tmp_path):
    path = write(tmp_path, variant(state_dir=None))
    with pytest.raises(ConfigError) as info:
        load(path, cwd=tmp_path)
    assert str(path) in str(info.value)
    assert info.value.key == "state_dir"


@pytest.mark.parametrize("text", ["", "- a\n- b\n", "just a string\n"])
def test_top_level_must_be_a_mapping(tmp_path, text):
    path = write(tmp_path, text)
    with pytest.raises(ConfigError, match="mapping"):
        load(path, cwd=tmp_path)


# --- schema_version handshake ----------------------------------------------------

def test_missing_schema_version_is_a_missing_required_key_not_a_migration():
    data = variant()
    del data["schema_version"]
    err = refused(data)
    assert err.key == "schema_version"
    assert "required" in str(err)
    assert "migrate-config" not in str(err)


def test_newer_schema_version_is_refused():
    err = refused(variant(schema_version=SCHEMA_VERSION + 1))
    assert err.key == "schema_version"
    assert "newer" in str(err)
    assert "migrate-config" not in str(err)


def test_older_schema_version_is_refused_with_migrate_config_as_the_paved_road():
    err = refused(variant(schema_version=0))
    assert err.key == "schema_version"
    assert "squatch migrate-config" in str(err)


@pytest.mark.parametrize("bad", ["1", 1.0, True, None])
def test_non_integer_schema_version_is_refused(bad):
    err = refused(variant(schema_version=bad))
    assert err.key == "schema_version"
    assert "integer" in str(err)


def test_handshake_runs_before_the_rest_of_the_schema():
    # An older config with other defects still gets the migration paved road:
    # the handshake owns the first verdict.
    err = refused({"schema_version": 0, "garbage": True})
    assert "migrate-config" in str(err)


# --- fail-closed validation ------------------------------------------------------

def test_missing_required_key_names_it():
    data = variant()
    del data["state_dir"]
    err = refused(data)
    assert err.key == "state_dir"
    assert "required" in str(err)


def test_missing_nested_required_key_names_the_path():
    data = variant()
    del data["providers"][0]["models_by_tier"]["max"]
    err = refused(data)
    assert err.key == "providers[0].models_by_tier.max"


@pytest.mark.parametrize("key", ["worktree_root", "scheduler", "notify", "review"])
def test_explicit_null_is_refused_even_where_a_default_exists(key):
    err = refused(variant(**{key: None}))
    assert err.key == key
    assert "null" in str(err)


def test_explicit_nested_null_is_refused_naming_the_path():
    data = variant()
    data["providers"][1]["auth"] = None
    err = refused(data)
    assert err.key == "providers[1].auth"


def test_unknown_top_level_key_is_refused():
    err = refused(variant(spend_ceiling=5))
    assert err.key == "spend_ceiling"


def test_unknown_nested_key_is_refused():
    data = variant()
    data["providers"][0]["limits"]["rpm"] = 10
    err = refused(data)
    assert err.key == "providers[0].limits.rpm"


def test_wrong_type_names_the_key():
    data = variant()
    data["providers"][0]["limits"]["concurrency"] = "two"
    err = refused(data)
    assert err.key == "providers[0].limits.concurrency"


def test_closed_vocabulary_is_enforced():
    data = variant()
    data["review"]["mechanical"][0]["severity"] = "medium"
    err = refused(data)
    assert err.key == "review.mechanical[0].severity"

    data = variant(routing_default_tier="ultra")
    assert refused(data).key == "routing_default_tier"

    data = variant()
    data["box_policy"] = {"suggestion": "pending"}
    assert refused(data).key == "box_policy.suggestion"


def test_every_defect_is_reported_at_once():
    data = variant(spend_ceiling=5)
    del data["state_dir"]
    err = refused(data)
    assert err.key == "state_dir"
    assert "spend_ceiling" in str(err)


# --- provider and routing rules --------------------------------------------------

def test_api_provider_is_refused_until_its_client_ships():
    data = variant()
    data["providers"][0]["kind"] = "api"
    err = refused(data)
    assert err.key == "providers[0].kind"
    assert "api client" in str(err)


def test_provider_kind_is_a_closed_vocabulary():
    data = variant()
    data["providers"][0]["kind"] = "sdk"
    assert refused(data).key == "providers[0].kind"


@pytest.mark.parametrize("secret", ["sk-ant-abc123", "lower_case", "HAS SPACE", ""])
def test_auth_must_be_an_env_var_name_never_a_literal_secret(secret):
    data = variant()
    data["providers"][0]["auth"] = secret
    err = refused(data)
    assert err.key == "providers[0].auth"
    assert "env" in str(err)


def test_provider_names_must_be_unique():
    data = variant()
    data["providers"][1]["name"] = "claude"
    err = refused(data)
    assert err.key == "providers[1].name"


def test_routing_candidate_must_name_a_declared_provider():
    data = variant()
    data["routing"][0]["candidates"][1]["provider"] = "gemini"
    err = refused(data)
    assert err.key == "routing[0].candidates[1].provider"
    assert "gemini" in str(err)


def test_regenerate_strategy_requires_argv_and_union_forbids_it():
    data = variant()
    del data["merge"]["strategies"][0]["argv"]
    assert refused(data).key == "merge.strategies[0].argv"

    data = variant()
    data["merge"]["strategies"][1]["argv"] = ["x"]
    assert refused(data).key == "merge.strategies[1].argv"


def test_positive_integer_floors():
    data = variant()
    data["providers"][0]["limits"]["concurrency"] = 0
    assert refused(data).key == "providers[0].limits.concurrency"
    assert refused(variant(scheduler={"max_unmerged": 0})).key == "scheduler.max_unmerged"
