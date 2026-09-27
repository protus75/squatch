"""Pause-boundary seeds and the shrinking Phase 3 successor."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket


REPO = Path(__file__).resolve().parent.parent
BATCH = {
    "dispatch-pause-boundary": ("phase3-continue-08",),
    "pause-resume-activation": ("dispatch-pause-boundary",),
    "phase3-continue-09": ("admission-holds-activation",),
}
OWNERSHIP = {
    "dispatch-pause-boundary": {"owns": ["tests/test_daemon_pause.py"], "hooks": [
        "squatch/daemon.py", "squatch/control.py", "squatch/drain.py", "tests/test_drain.py"]},
    "pause-resume-activation": {"owns": ["tests/test_control_cli.py"], "hooks": [
        "squatch/daemon.py", "squatch/control.py", "squatch/drain.py",
        "squatch/__main__.py", "tests/test_daemon_pause.py",
        "tests/test_daemon_composition.py"]},
    "admission-holds-activation": {"owns": [], "hooks": [
        "squatch/mergequeue.py", "squatch/merge.py", "squatch/__main__.py",
        "eval/shakeout/bench.py",
        "tests/test_mergequeue.py", "tests/test_merge.py",
        "tests/test_daemon_composition.py"]},
    "phase3-continue-09": {"owns": ["tickets", "tests/test_seeded_phase3_09.py"], "hooks": []},
}
CONTEXT = {
    "dispatch-pause-boundary": ("tests/test_seeded_phase3_core.py", "squatch/daemon.py",
        "squatch/control.py", "squatch/drain.py", "tests/test_drain.py"),
    "pause-resume-activation": ("tests/test_seeded_phase3_core.py", "squatch/daemon.py",
        "squatch/control.py", "squatch/__main__.py", "tests/test_daemon_composition.py"),
    "phase3-continue-09": ("tests/test_seeded_phase3_core.py", "squatch/control.py",
        "squatch/daemon.py", "squatch/driver.py"),
}
# Permanent render fixtures: later growth must not redden historical seed tests.
EXISTING_AT_AUTHORING = {
    "squatch/driver.py": 9738,
    "tests/test_seeded_phase3_core.py": 5877, "squatch/daemon.py": 6828,
    "squatch/control.py": 7283, "squatch/drain.py": 22833, "tests/test_drain.py": 35720,
    "squatch/mergequeue.py": 12921, "squatch/merge.py": 23414,
    "squatch/__main__.py": 10674,
    "tests/test_mergequeue.py": 34441, "tests/test_daemon_composition.py": 7625,
    "tests/test_merge.py": 21750,
}
NEW_PATH_OWNERS = {
    "tests/test_daemon_pause.py": "dispatch-pause-boundary",
    "tests/test_control_cli.py": "pause-resume-activation",
    "tests/test_seeded_phase3_09.py": "phase3-continue-09",
}
FULL = (("dispatch-pause-boundary", "pause-resume-activation"),
        ("kill-signal-journal", "kill-executor-abort"),
        ("kill-worker-stop", "kill-failure-suppression"), ("kill-cli-activation",),
        ("heartbeat",), ("restart-timers",), ("flake-detection", "flake-release"),
        ("journal-roll", "storm-ledger"),
        ("storm-producer-wiring", "storm-notification-activation"),
        ("storm-dispatch-hold",), ("checkpoint-push",), ("daemon-soak",),
        ("soak-run",), ("phase3-exit",))
SUCCESSOR = FULL[1:]


def _path(stem):
    return REPO / TICKETS_DIR / stem / TICKET_FILE


def _section(stem, name):
    lines = _path(stem).read_text().splitlines()
    start = lines.index(f"## {name}") + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


def _ticket(stem):
    return lint_ticket(_path(stem).read_text(), stem=stem, repo=REPO,
                       plan=(REPO / PLAN_FILE).read_text(),
                       resolve_stem=lambda candidate: _path(candidate).is_file())


def _ownership(stem):
    blocks = [yaml.safe_load(item) for item in re.findall(
        r"```yaml\n(.*?)\n```", _section(stem, "Scope in"), re.S)]
    [block] = [block for block in blocks if isinstance(block, dict) and "ownership" in block]
    return block["ownership"]


def test_exact_pause_seeds_edges_budgets_cap_fences_and_contexts():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert tuple(BATCH) == ("dispatch-pause-boundary", "pause-resume-activation",
                            "phase3-continue-09")
    assert len(BATCH) == config.seeding.max_seeds_per_admission == 3
    for stem, depends in BATCH.items():
        ticket = _ticket(stem)
        assert (ticket.source, ticket.priority) == ("seed", "P1")
        assert ticket.state in {"confirmed", "rejected"}
        assert ticket.depends == depends and ticket.plan_sections == ("20",)
        assert (ticket.agent_tier, ticket.agent_effort) == ("medium", "medium")
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
        assert ticket.stuck_minutes <= config.drain.max_ticket_minutes == 180
        assert ticket.context == CONTEXT[stem]
        assert ticket.scope_fence == tuple(OWNERSHIP[stem]["owns"] + OWNERSHIP[stem]["hooks"])


def test_ownership_existing_closure_and_exact_new_path_owners():
    assert set(EXISTING_AT_AUTHORING).isdisjoint(NEW_PATH_OWNERS)
    assert NEW_PATH_OWNERS == {
        "tests/test_daemon_pause.py": "dispatch-pause-boundary",
        "tests/test_control_cli.py": "pause-resume-activation",
        "tests/test_seeded_phase3_09.py": "phase3-continue-09",
    }
    for stem in BATCH:
        ticket = _ticket(stem)
        assert set(ticket.context) <= set(EXISTING_AT_AUTHORING)
        assert set(ticket.context).isdisjoint({"squatch/specs.py", "specs/implement.md"})
        for path in ticket.scope_fence:
            if path in EXISTING_AT_AUTHORING and path not in {"squatch/merge.py", "squatch/drain.py"}:
                assert path in ticket.context, (stem, path)
            elif path not in {"tickets", "squatch/merge.py", "squatch/drain.py"}:
                assert NEW_PATH_OWNERS[path] in {stem, "dispatch-pause-boundary"}
        assert _ownership(stem) == {stem: OWNERSHIP[stem]}
    assert "tests/test_daemon_pause.py" not in CONTEXT["pause-resume-activation"]


def test_predecessor_closure_and_preservation_only_exclusions_are_pinned():
    activation = _ticket("pause-resume-activation")
    for path in ("tests/test_daemon_pause.py", "tests/test_daemon_composition.py"):
        assert path in activation.scope_fence
        assert any(path in argv for argv in activation.verification)
    assert "squatch/drain.py" in activation.scope_fence
    assert "squatch/drain.py" not in activation.context
    assert any("tests/test_drain.py" in argv for argv in activation.verification)
    holds = _ticket("admission-holds-activation")
    assert holds.depends == ("pause-resume-activation",)
    assert holds.scope_fence == tuple(
        OWNERSHIP["admission-holds-activation"]["hooks"])
    assert "tests/test_mergequeue.py" in holds.context
    assert any("tests/test_mergequeue.py" in argv for argv in holds.verification)
    assert "squatch/__main__.py" in holds.context
    assert "tests/test_daemon_composition.py" in holds.scope_fence
    assert "tests/test_merge.py" in holds.scope_fence
    assert "eval/shakeout/bench.py" in holds.scope_fence
    assert "squatch/__main__.py" in activation.context
    boundary = _ticket("dispatch-pause-boundary")
    assert {"squatch/drain.py", "tests/test_drain.py"} <= set(boundary.scope_fence)
    assert any("tests/test_drain.py" in argv for argv in boundary.verification)
    for stem in ("dispatch-pause-boundary", "pause-resume-activation"):
        ticket = _ticket(stem)
        for preservation in ("tests/test_daemon_tasks.py", "tests/test_control.py"):
            assert any(preservation in argv for argv in ticket.verification)
            assert preservation not in ticket.context
            assert preservation not in ticket.scope_fence


def test_successor_has_exact_kill_ownership():
    blocks = [yaml.safe_load(item) for item in re.findall(
        r"```yaml\n(.*?)\n```", _section("phase3-continue-09", "Scope in"), re.S)]
    [ownership] = [block["kill_ownership"] for block in blocks
                   if isinstance(block, dict) and "kill_ownership" in block]
    assert ownership == {
        "kill-signal-journal": {
            "owns": ["tests/test_kill_signal_journal.py"],
            "hooks": ["squatch/control.py", "squatch/daemon.py"]},
        "kill-executor-abort": {
            "owns": ["tests/test_kill_executor_abort.py"],
            "hooks": ["squatch/daemon.py", "squatch/driver.py"]},
        "phase3-continue-10": {
            "owns": ["tickets", "tests/test_seeded_phase3_10.py"], "hooks": []},
    }
    for entry in ownership.values():
        assert "squatch/__main__.py" not in entry["owns"] + entry["hooks"]
    assert set(CONTEXT["phase3-continue-09"]).isdisjoint(NEW_PATH_OWNERS)


def test_successor_is_shrinking_and_synthetic_renders_fit_headroom():
    assert SUCCESSOR == FULL[1:]
    blocks = [yaml.safe_load(item) for item in re.findall(
        r"```yaml\n(.*?)\n```", _section("phase3-continue-08", "Scope in"), re.S)]
    [admissions] = [block for block in blocks if isinstance(block, list)]
    assert tuple(tuple(row) for row in admissions) == FULL
    [ownership] = [block["pause_ownership"] for block in blocks
                   if isinstance(block, dict) and "pause_ownership" in block]
    assert ownership == OWNERSHIP
    stems = [stem for row in FULL for stem in row]
    assert len(stems) == len(set(stems))
    block = _section("phase3-continue-09", "Scope in").split("```yaml\n", 1)[1].split("\n```", 1)[0]
    assert tuple(tuple(row) for row in yaml.safe_load(block)) == SUCCESSOR
    spec = load_spec(REPO / "specs" / "implement.md")
    plan = (REPO / PLAN_FILE).read_text()
    limit = RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM
    for stem, paths in CONTEXT.items():
        context = "".join(f"### {path}\n{'x' * EXISTING_AT_AUTHORING[path]}\n" for path in paths)
        workspace = f"stem: {stem}\nbranch: {stem}\nrun record: tickets/{stem}/{RUN_RECORD}\n"
        prompt = spec.render({"workspace": DataBlock("engine", workspace),
                              "ticket": DataBlock("host", _path(stem).read_text()),
                              "context": DataBlock("host", context)}, plan=plan,
                             plan_sections=("20",), effort="max")
        assert len(prompt) <= limit, (stem, len(prompt), limit)
