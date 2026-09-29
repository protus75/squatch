"""The fixture host is deliberately closed, deterministic, and zero-spend."""

import asyncio
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml

from squatch.config import parse
from squatch.git import Git
from squatch.llm import LLMRequest
from squatch.providers import CliClient, ProviderRuntime, Registry
from squatch.redact import Redactor
from squatch.seams import LocalFilesystem, SubprocessExec


ROOT = Path(__file__).resolve().parents[1] / "hosts" / "fixture"


class Timers:
    def pending(self, prefix):
        return None

    def arm(self, key, at):
        raise AssertionError("the zero-spend fixture must not cool down")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_profile_is_deterministic_and_has_a_closed_zero_spend_provider_row():
    config = parse(yaml.safe_load((ROOT / "config.yaml").read_text()), source="fixture")
    registry = Registry(config, source="fixture")
    assert config.schema_version == 1
    assert config.report_inbox == Path(".squatch/report-inbox")
    assert [(row.code, row.argv, row.severity) for row in config.review.mechanical] == [
        ("fixture-replay", ["python", "bin/fixture-replay"], "hard")]
    for surface in ("author", "implement", "review"):
        resolved = registry.resolve("medium", surface)
        assert resolved.provider.name == "codex"
        assert resolved.provider.limits.est_cost_per_call_usd == 0.0
        assert resolved.model == "fixture-medium"


def test_closed_scenarios_preserve_the_base_regression_but_not_the_escape():
    replay = load_module("_fixture_replay_test", ROOT / "replay.py").replay
    scenarios = json.loads((ROOT / "scenarios.json").read_text())
    assert [(item["name"], item["ticket_stem"]) for item in scenarios] == [
        ("deterministic-app", "fixture-deterministic-app"),
        ("report-to-regression", "fixture-regression-fix"),
        ("machine-introduced-escape", "fixture-machine-escape"),
    ]
    results = replay()
    assert [(result["scenario"], result["outcome"]) for result in results] == [
        ("deterministic-app", "pass"), ("report-to-regression", "reproduced"),
        ("machine-introduced-escape", "pass")]
    assert results[1]["actual"] == "bird" and results[1]["expected"] == "animal"
    assert results[2]["actual"] == "contained"
    output = subprocess.run(
        [str(ROOT / "bin" / "fixture-replay"), "--scenario", "report-to-regression"],
        text=True, capture_output=True)
    assert output.returncode == 1
    assert json.loads(output.stdout)[0]["actual"] == "bird"


def test_reports_are_full_version_one_records_with_bounded_replay_evidence():
    required = {"schema_version", "origin", "summary", "signature", "app_commit",
                "app_version", "implicated_paths", "replay_file", "replay_bytes",
                "log_excerpt", "log_excerpt_bytes"}
    reports = sorted((ROOT / "reports").glob("*.json"))
    assert [path.name for path in reports] == ["escape-report.json", "regression-report.json"]
    for report_path in reports:
        report = json.loads(report_path.read_text())
        assert set(report) == required
        assert report["schema_version"] == 1
        assert report["origin"] in {"self_diagnosed", "player"}
        assert all(isinstance(report[key], str) and report[key]
                   for key in ("summary", "signature", "app_commit", "app_version"))
        assert 0 < len(report["implicated_paths"]) <= 32
        replay_path = ROOT / report["replay_file"]
        assert replay_path.is_file()
        assert replay_path.stat().st_size == report["replay_bytes"] <= 1024 * 1024
        evidence = json.loads(replay_path.read_text())
        assert set(evidence) == {"initial_state", "actions"}
        assert isinstance(evidence["initial_state"], dict) and evidence["initial_state"]
        assert isinstance(evidence["actions"], list) and evidence["actions"]
        assert len(report["log_excerpt"].encode()) == report["log_excerpt_bytes"] <= 64 * 1024


class FixtureProcess(SubprocessExec):
    async def run(self, argv, **kwargs):
        # Assert before execution so a PATH regression cannot launch a paid CLI.
        assert argv[0] == "codex"
        assert shutil.which("codex", path=kwargs["env"]["PATH"]) == str(ROOT / "bin" / "codex")
        return await super().run(argv, **kwargs)


def _client(root: Path, state: Path):
    config = parse(yaml.safe_load((root / "config.yaml").read_text()), source="fixture")
    runtime = ProviderRuntime(Registry(config, source="fixture"), timers=Timers(),
                              clock=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))
    launcher = load_module("_fixture_client_env", ROOT / "serve.py")
    env = launcher.launch_environment(os.environ)
    return CliClient(runtime, process=FixtureProcess(), fs=LocalFilesystem(), env=env,
                     redact=Redactor.from_config(config, env), state_dir=state,
                     cwd=root)


def _call(client, surface: str, scenario: str, worktree: Path | None = None):
    rendered = (f"squatch prompt: surface={surface} spec_version=1.1\n"
                f"You are the {surface}; the implementer also appears in review prose.\n"
                f"fixture-scenario: {scenario}\n")
    result = asyncio.run(client.call(LLMRequest(
        surface=surface, rendered=rendered, tier="medium", effort="medium",
        ticket=scenario, worktree=worktree)))
    assert result.usd == 0.0
    assert result.input_tokens == result.output_tokens == 0
    return result


@pytest.mark.parametrize("scenario,stem", [
    ("deterministic-app", "fixture-deterministic-app"),
    ("report-to-regression", "fixture-regression-fix"),
    ("machine-introduced-escape", "fixture-machine-escape"),
])
def test_scripted_cli_serves_scenario_specific_author_implement_and_review(
        tmp_path, monkeypatch, scenario, stem):
    for key, value in {"GIT_AUTHOR_NAME": "fixture", "GIT_COMMITTER_NAME": "fixture",
                       "GIT_AUTHOR_EMAIL": "f@invalid", "GIT_COMMITTER_EMAIL": "f@invalid"}.items():
        monkeypatch.setenv(key, value)
    repo = tmp_path / "main"
    shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns("__pycache__"))
    git = Git(SubprocessExec(), env=os.environ, timeout=30)
    asyncio.run(git.init(repo))
    files = [str(path.relative_to(repo)) for path in repo.rglob("*")
             if path.is_file() and ".git" not in path.parts]
    asyncio.run(git.add(repo, files))
    base = asyncio.run(git.commit(repo, "fixture base", files))
    worktree = tmp_path / "worktree"
    asyncio.run(git.worktree_add(repo, worktree, stem, base))
    try:
        client = _client(worktree, tmp_path / "state" / scenario)
        authored = json.loads(_call(client, "author", scenario).text)
        assert authored["stem"] == stem
        assert f"fixture-scenario: {scenario}" in authored["ticket"]
        assert "Plan contract" not in authored["ticket"]
        assert replay_command(worktree).returncode == 0
        if scenario == "report-to-regression":
            before = replay_command(worktree, scenario)
            assert before.returncode == 1
            assert json.loads(before.stdout)[0]["actual"] == "bird"
            assert not (worktree / "scenario-output/regression_check.py").exists()
            assert "- carries: scenario-output/regression_check.py" in authored["ticket"]
            assert "carries: app.py" not in authored["ticket"]
        elif scenario == "machine-introduced-escape":
            assert replay_command(worktree, scenario).returncode == 0

        implemented = json.loads(_call(client, "implement", scenario, worktree).text)
        assert implemented["verdict"] == "implemented"
        head = asyncio.run(git.rev_parse(worktree, "HEAD"))
        changes = asyncio.run(git.diff_names(repo, base, head))
        assert changes, "each canned implement must commit a non-empty diff"
        assert not any(path.startswith("tickets/") for path in changes)
        assert (worktree / "tickets" / stem / "run.md").is_file()
        assert (worktree / "scenario-output" / f"{scenario}.txt").is_file()
        reviewed = json.loads(_call(client, "review", scenario).text)
        assert reviewed == {"verdict": "approve",
                            "summary": f"approved canned {scenario} change", "findings": []}
        assert replay_command(worktree).returncode == 0
        if scenario == "report-to-regression":
            assert replay_command(worktree, scenario).returncode == 0
            command = [sys.executable, "scenario-output/regression_check.py"]
            head_result = subprocess.run(command, cwd=worktree, capture_output=True, text=True)
            assert head_result.returncode == 0
            # Overlay ONLY the carried branch-added test onto the untouched base.
            (repo / "scenario-output").mkdir()
            shutil.copyfile(worktree / command[1], repo / command[1])
            base_result = subprocess.run(command, cwd=repo, capture_output=True, text=True)
            assert base_result.returncode == 1
            assert json.loads(base_result.stdout)[0]["actual"] == "bird"
            assert (repo / "app.py").read_bytes() == (ROOT / "app.py").read_bytes()
        elif scenario == "machine-introduced-escape":
            escaped = replay_command(worktree, scenario)
            assert escaped.returncode == 1
            assert json.loads(escaped.stdout)[0]["actual"] == "escaped"
    finally:
        asyncio.run(git.worktree_remove(repo, worktree))


def replay_command(root, scenario=None):
    argv = [sys.executable, str(root / "bin/fixture-replay")]
    if scenario:
        argv += ["--scenario", scenario]
    return subprocess.run(argv, cwd=root, capture_output=True, text=True)


def test_fixture_serve_pins_scripted_codex_and_strips_provider_keys():
    launcher = load_module("_fixture_serve_test", ROOT / "serve.py")
    source = {"PATH": os.environ.get("PATH", ""), "OPENAI_API_KEY": "paid",
              "CODEX_API_KEY": "paid", "ANTHROPIC_API_KEY": "paid", "KEEP": "yes"}
    env = launcher.launch_environment(source)
    assert shutil.which("codex", path=env["PATH"]) == str(ROOT / "bin" / "codex")
    assert env["KEEP"] == "yes"
    assert launcher.PROVIDER_KEYS.isdisjoint(env)
    assert os.access(ROOT / "bin" / "fixture-serve", os.X_OK)


def test_scripted_cli_fails_closed_on_unknown_surface_or_scenario():
    for prompt in ("squatch prompt: surface=triage spec_version=1.1\nfixture-scenario: deterministic-app\n",
                   "squatch prompt: surface=review spec_version=1.1\nfixture-scenario: x\n",
                   "squatch prompt: surface=review spec_version=1.1\n",
                   "squatch prompt: surface=review spec_version=1.1\n"
                   "fixture-scenario: deterministic-app\nfixture-scenario: report-to-regression\n"):
        failed = subprocess.run([str(ROOT / "bin" / "codex")], input=prompt, text=True,
                                capture_output=True)
        assert failed.returncode != 0
        event = json.loads(failed.stdout)
        assert event["type"] == "turn.failed"
