"""Phase 5 closes only from committed retro, provenance, and baseline evidence."""

import ast
import asyncio
import hashlib
import json
import os
import re
from pathlib import Path

import test_baseline
import test_retro_box

from squatch.artifacts import GATE_CODES
from squatch.baseline import NO_GO, REVOKED, resolve_baseline
from squatch.git import Git
from squatch.seams import SubprocessExec


REPO = Path(__file__).resolve().parent.parent
PHASE5_STEMS = (
    "retro-drain-invoker",
    "retro-box-activation",
    "scorecard-reporting",
    "status-projection",
    "baseline-binding-reader",
    "retro-doctor-cli",
    "phase5-continue",
    "phase5-continue-02",
    "phase5-continue-03",
    "phase5-continue-04",
)
CORE = ("core-renderer", "core-drift-classifier", "phase6-continue")
RETRO_PATH = re.compile(r"tickets/retro/[0-9]{6}\.md\Z")
SCORECARD_ROW = re.compile(
    r"^\| `([^`]+)` \| (\d+) \| (\d+) \| (\d+) \| (\d+) \| "
    r"([0-9]+\.[0-9]+) \| ([0-9]+\.[0-9]+) \| (yes|no) \|$"
)


def _git():
    return Git(SubprocessExec(), env=os.environ, timeout=30)


def _blob_id(data):
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def _assert_committed(path):
    data = (REPO / path).read_bytes()
    committed = asyncio.run(_git().rev_parse(REPO, f"HEAD:{path}"))
    assert _blob_id(data) == committed
    return data


def _checks(stem):
    path = f"tickets/{stem}/checks.json"
    data = json.loads(_assert_committed(path))
    assert data["stem"] == stem
    assert data["checks"]
    assert all(check["verdict"] == "pass" and not check["bypassed"]
               for check in data["checks"])
    return data


async def _first_parent_history():
    output = await _git()._run(
        REPO, "log", "--first-parent", "--format=%H%x00%B%x00")
    fields = output.split("\0")
    return tuple((fields[index].strip(), fields[index + 1])
                 for index in range(0, len(fields) - 1, 2)
                 if fields[index].strip())


async def _adding_commit(path, *, through):
    output = await _git()._run(
        REPO, "log", "--first-parent", "--diff-filter=A", "--format=%H",
        through, "--", path)
    commits = tuple(line for line in output.splitlines() if line)
    assert len(commits) == 1, (path, commits)
    return commits[0]


async def _tracked_retro_reports(rev):
    output = await _git()._run(
        REPO, "ls-tree", "-r", "--name-only", rev, "--", "tickets/retro")
    return tuple(sorted(path for path in output.splitlines()
                        if RETRO_PATH.fullmatch(path)))


def test_latest_committed_forced_report_closes_the_phase5_window():
    history = asyncio.run(_first_parent_history())
    order = {commit: index for index, (commit, _message) in enumerate(history)}
    phase_exit = asyncio.run(_adding_commit(
        "tests/test_phase5_exit.py", through="HEAD"))
    phase5_merges = {
        stem: commit
        for commit, message in history
        for stem in PHASE5_STEMS
        if f"squatch-ticket: {stem}" in message.splitlines()
    }
    assert set(phase5_merges) == set(PHASE5_STEMS)
    latest_phase5_merge = min(phase5_merges.values(), key=order.__getitem__)

    candidates = []
    for path in asyncio.run(_tracked_retro_reports(phase_exit)):
        adding_commit = asyncio.run(_adding_commit(path, through=phase_exit))
        if order[phase_exit] <= order[adding_commit] < order[latest_phase5_merge]:
            candidates.append((path, adding_commit))
    assert candidates
    latest, report_commit = max(candidates)
    report = _assert_committed(latest).decode()

    assert order[phase_exit] <= order[report_commit] < order[latest_phase5_merge]
    assert "- Trigger: `phase-exit`" in report
    assert "- Trigger: `manual`" not in report
    assert "## Surface scorecard" in report
    assert re.search(r"- Metered spend: \$[0-9]+\.[0-9]+; tokens: [0-9]+$", report, re.M)
    assert "`phase5-continue-04`" in report
    assert "`retro-doctor-cli`" in report

    rows = [match.groups() for line in report.splitlines()
            if (match := SCORECARD_ROW.fullmatch(line))]
    assert rows
    assert all(surface in GATE_CODES for surface, *_rest in rows)
    assert all(int(escapes) == 0 for _surface, _evaluated, _catches, escapes,
               _bypasses, _catch_rate, _escape_rate, _prune in rows)


def test_forced_producer_and_all_named_phase5_dependencies_are_committed_green():
    invoker = _checks("retro-drain-invoker")
    verification = next(check for check in invoker["checks"]
                        if check["code"] == "verification")
    assert any("tests/test_retro.py" in command["argv"]
               for command in verification["commands"])
    retro_test = _assert_committed("tests/test_retro.py").decode()
    assert 'pytest.mark.parametrize("trigger", ["quiescence", "phase-exit"])' in retro_test
    drain = _assert_committed("squatch/drain.py").decode()
    assert 'await retro("phase-exit", True)' in drain

    for stem in PHASE5_STEMS:
        _assert_committed(f"tickets/{stem}/ticket.md")
        _checks(stem)
    for stem in CORE:
        assert (REPO / "tickets" / stem / "ticket.md").is_file()


def test_committed_retro_provenance_fixture_and_check_are_reexercised(tmp_path):
    before = tuple(sorted((REPO / "tickets" / "retro").glob("*.md")))
    _assert_committed("tests/test_retro_box.py")
    checks = _checks("retro-box-activation")
    verification = next(check for check in checks["checks"]
                        if check["code"] == "verification")
    assert any("tests/test_retro_box.py" in command["argv"]
               for command in verification["commands"])

    test_retro_box.test_retro_proposal_identity_origin_replay_and_distinctions(tmp_path)
    test_retro_box.test_merge_uses_only_unique_journal_bridge_and_exact_success_predicate()
    assert tuple(sorted((REPO / "tickets" / "retro").glob("*.md"))) == before


def test_committed_baseline_fixture_reexercises_supervised_shapes(tmp_path):
    _assert_committed("tests/test_baseline.py")
    checks = _checks("baseline-binding-reader")
    verification = next(check for check in checks["checks"]
                        if check["code"] == "verification")
    assert any("tests/test_baseline.py" in command["argv"]
               for command in verification["commands"])

    cfg = test_baseline.config()
    (tmp_path / "no-go").mkdir()
    current_specs = test_baseline.specs(tmp_path / "no-go")
    no_go = test_baseline.event({"kind": "review_baseline", "verdict": "NO_GO"})
    resolution = resolve_baseline(cfg, (no_go,), specs_dir=current_specs)
    assert (resolution.state, resolution.binds) == (NO_GO, False)

    (tmp_path / "drift").mkdir()
    drifted_specs = test_baseline.specs(tmp_path / "drift")
    recorded_go = test_baseline.go(cfg)
    (drifted_specs / "review.md").write_text(
        (drifted_specs / "review.md").read_text().replace(
            'version: "1.0"', 'version: "2.0"', 1))
    resolution = resolve_baseline(cfg, (recorded_go,), specs_dir=drifted_specs)
    assert (resolution.state, resolution.binds) == (REVOKED, False)


def test_exit_proof_has_no_live_journal_or_repository_report_writer():
    source = Path(__file__).read_text()
    tree = ast.parse(source)
    imports = {(node.module, alias.name) for node in ast.walk(tree)
               if isinstance(node, ast.ImportFrom)
               for alias in node.names}
    calls = {node.func.id for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert not any(module == "squatch.journal" for module, _name in imports)
    assert calls.isdisjoint({"Journal", "read_events"})
    assert "." + "squatch/state" not in source
    assert "tickets/retro/" + "000011" not in source
