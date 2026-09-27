"""Background-consumer/control-inbox seeds and their shrinking successor."""

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
    "background-consumers": ("phase3-continue-07",),
    "control-inbox": ("background-consumers",),
    "phase3-continue-08": ("background-consumers", "control-inbox"),
}
CONTEXT = {
    "background-consumers": (
        "squatch/daemon.py", "squatch/watcher.py", "squatch/scheduler.py",
        "squatch/triage.py", "squatch/box.py", "squatch/rework.py",
        "tests/test_daemon_composition.py"),
    "control-inbox": (
        "squatch/daemon.py", "squatch/seams.py", "tests/test_daemon_composition.py",
        "tests/test_seams.py"),
    "phase3-continue-08": (
        "tests/test_seeded_phase3_core.py", "squatch/daemon.py", "squatch/__main__.py",
        "tests/test_daemon_composition.py", "tests/test_mergequeue.py"),
}
OWNERSHIP = {
    "background-consumers": {"owns": ["tests/test_daemon_tasks.py"],
                             "hooks": ["squatch/daemon.py"]},
    "control-inbox": {"owns": ["squatch/control.py", "tests/test_control.py"],
                      "hooks": ["squatch/daemon.py", "squatch/seams.py",
                                "tests/test_daemon_tasks.py", "tests/test_seams.py"]},
    "phase3-continue-08": {"owns": ["tickets", "tests/test_seeded_phase3_08.py"],
                            "hooks": []},
}
PAUSE_OWNERSHIP = {
    "dispatch-pause-boundary": {"owns": ["tests/test_daemon_pause.py"], "hooks": [
        "squatch/daemon.py", "squatch/control.py", "squatch/drain.py",
        "tests/test_drain.py"]},
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
EXISTING_AT_AUTHORING = {
    "tests/test_seeded_phase3_core.py": 5877, "squatch/daemon.py": 3679,
    "squatch/watcher.py": 529, "squatch/scheduler.py": 1751,
    "squatch/triage.py": 14609, "squatch/box.py": 12324,
    "squatch/rework.py": 8651, "squatch/__main__.py": 10674,
    "tests/test_daemon_composition.py": 7625, "tests/test_mergequeue.py": 34441,
    "squatch/seams.py": 4575, "tests/test_seams.py": 4442,
}
NEW_AT_AUTHORING = {"squatch/control.py", "tests/test_daemon_tasks.py", "tests/test_control.py",
                    "tests/test_seeded_phase3_08.py"}
FULL = (
    ("background-consumers", "control-inbox"), ("dispatch-pause-boundary", "pause-resume-activation"),
    ("kill-signal-journal", "kill-executor-abort"), ("kill-worker-stop", "kill-failure-suppression"),
    ("kill-cli-activation",), ("heartbeat",), ("restart-timers",), ("flake-detection", "flake-release"),
    ("journal-roll", "storm-ledger"), ("storm-producer-wiring", "storm-notification-activation"),
    ("storm-dispatch-hold",), ("checkpoint-push",), ("daemon-soak",), ("soak-run",), ("phase3-exit",))
SUCCESSOR = (
    ("dispatch-pause-boundary", "pause-resume-activation"),
    ("kill-signal-journal", "kill-executor-abort"), ("kill-worker-stop", "kill-failure-suppression"),
    ("kill-cli-activation",), ("heartbeat",), ("restart-timers",), ("flake-detection", "flake-release"),
    ("journal-roll", "storm-ledger"), ("storm-producer-wiring", "storm-notification-activation"),
    ("storm-dispatch-hold",), ("checkpoint-push",), ("daemon-soak",), ("soak-run",), ("phase3-exit",))
PAUSE_EDGES = {
    "dispatch-pause-boundary": ("phase3-continue-08",),
    "pause-resume-activation": ("dispatch-pause-boundary",),
    "phase3-continue-09": ("admission-holds-activation",),
}


def _path(stem):
    return REPO / TICKETS_DIR / stem / TICKET_FILE


def _ticket(stem):
    return lint_ticket(_path(stem).read_text(), stem=stem, repo=REPO,
                       plan=(REPO / PLAN_FILE).read_text(),
                       resolve_stem=lambda candidate: _path(candidate).is_file())


def _section(stem, name):
    lines = _path(stem).read_text().splitlines()
    start = lines.index(f"## {name}") + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


def _yaml(stem):
    return [yaml.safe_load(block) for block in re.findall(
        r"```yaml\n(.*?)\n```", _section(stem, "Scope in"), re.S)]


def test_exact_seeds_edges_budgets_cap_fences_and_contexts():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert tuple(BATCH) == ("background-consumers", "control-inbox", "phase3-continue-08")
    assert len(BATCH) == config.seeding.max_seeds_per_admission == 3
    for stem, depends in BATCH.items():
        ticket = _ticket(stem)
        assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
        assert ticket.depends == depends and ticket.plan_sections == ("20",)
        assert (ticket.agent_tier, ticket.agent_effort) == ("medium", "medium")
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
        assert ticket.stuck_minutes <= config.drain.max_ticket_minutes == 180
        assert ticket.context == CONTEXT[stem]
        assert ticket.scope_fence == tuple(OWNERSHIP[stem]["owns"] + OWNERSHIP[stem]["hooks"])
        if stem != "phase3-continue-08":
            [record] = [block["ownership"] for block in _yaml(stem)
                        if isinstance(block, dict) and "ownership" in block]
            assert record == {stem: OWNERSHIP[stem]}


def test_authoring_registry_is_closed_and_context_is_read_only():
    assert NEW_AT_AUTHORING == {"squatch/control.py", "tests/test_daemon_tasks.py",
                                "tests/test_control.py", "tests/test_seeded_phase3_08.py"}
    assert set(EXISTING_AT_AUTHORING).isdisjoint(NEW_AT_AUTHORING)
    for stem in BATCH:
        ticket = _ticket(stem)
        assert set(ticket.context) <= set(EXISTING_AT_AUTHORING)
        assert set(ticket.context).isdisjoint(NEW_AT_AUTHORING | {"squatch/specs.py", "specs/implement.md"})
        for path in ticket.scope_fence:
            if path in EXISTING_AT_AUTHORING:
                assert path in ticket.context
    assert OWNERSHIP["background-consumers"]["owns"] == ["tests/test_daemon_tasks.py"]
    assert OWNERSHIP["control-inbox"]["owns"] == ["squatch/control.py", "tests/test_control.py"]
    assert OWNERSHIP["phase3-continue-08"]["owns"] == ["tickets", "tests/test_seeded_phase3_08.py"]
    background = _ticket("background-consumers")
    for path in ("squatch/watcher.py", "squatch/scheduler.py", "squatch/triage.py",
                 "squatch/box.py", "squatch/rework.py"):
        assert path in background.context and path not in background.scope_fence


def test_seed_prose_pins_consumer_and_predecessor_boundaries():
    background = _section("background-consumers", "Scope in")
    background_criteria = _section("background-consumers", "Acceptance criteria")
    control = _section("control-inbox", "Scope in")
    for phrase in ("three injected awaitable callbacks", "Callback construction remains deferred",
                   "starts all loops", "owns their repetition and lifetime", "awaits them at shutdown",
                   "priority snapshot to `Watcher.observed`", "post-admission Rework handoff", "callback-supplied SHA",
                   "`Triage.run` pass", "each consumer lifetime independently", "clean shutdown",
                   "cancellation", "sibling cleanup", "re-raises that exception"):
        assert phrase in background
    for phrase in ("one independently named test for each consumer lifetime",
                   "cancels and awaits siblings", "re-raises that exception"):
        assert phrase in background_criteria
    assert "tests/test_daemon_tasks.py" in _ticket("control-inbox").scope_fence
    assert "tests/test_daemon_tasks.py" not in _ticket("control-inbox").context
    verification = _section("control-inbox", "Verification")
    assert "uv run pytest" in verification and "tests/test_daemon_tasks.py" in verification
    for stem in ("background-consumers", "control-inbox"):
        assert "tests/test_daemon_composition.py" in _section(stem, "Verification")
        assert "Preserve `tests/test_daemon_composition.py` unchanged" in _section(stem, "Scope in")
    assert "crash-safe" in control and "exactly once" in control and "decision is journaled before" in control
    for phrase in ("lock-held journal", "restart-unique", "release binds a hold instance",
                   "Stale lifecycle requests and releases predating a hold never affect later identities",
                   "Prove replay at crash points"):
        assert phrase in control


def test_continuation_pins_pause_closure_and_shrinking_suffix():
    scope = _section("phase3-continue-08", "Scope in")
    [ownership] = [block for block in _yaml("phase3-continue-08")
                   if isinstance(block, dict) and "pause_ownership" in block]
    assert ownership["pause_ownership"] == PAUSE_OWNERSHIP
    assert _ticket("phase3-continue-08").context[-1] == "tests/test_mergequeue.py"
    assert "squatch/__main__.py" in _ticket("phase3-continue-08").context
    for predecessor in ("tests/test_daemon_composition.py", "tests/test_mergequeue.py"):
        assert predecessor in scope
    for stem, depends in PAUSE_EDGES.items():
        assert stem in scope and depends[0] in scope
    assert "medium/medium" in scope and "75m/150m" in scope and "configured cap 3" in scope
    for phrase in (
            "Author confirmed `dispatch-pause-boundary`, `pause-resume-activation`, and `phase3-continue-09` seeds",
            "Derive each activation fence as its owns followed by its hooks",
            "exact new-path owners", "successor suffix equality",
            "The activation seeds include their now-existing fenced predecessor paths in Context",
            "explicit on-demand inspection exception required by render headroom",
            "preservation-only suites remain outside fences and Context",
            "Sibling-new paths remain outside this continuation Context"):
        assert phrase in scope
    assert SUCCESSOR == FULL[1:]
    [rendered] = [block for block in _yaml("phase3-continue-08") if isinstance(block, list)]
    assert tuple(tuple(row) for row in rendered) == SUCCESSOR
    assert "max-effort render headroom" in scope and "authoring-time existing-size map" in scope


def test_synthetic_max_render_uses_only_pinned_sizes():
    spec = load_spec(REPO / "specs" / "implement.md")
    plan = (REPO / PLAN_FILE).read_text()
    for stem in BATCH:
        ticket = _ticket(stem)
        context = "".join(f"### {path}\n{'x' * EXISTING_AT_AUTHORING[path]}\n" for path in ticket.context)
        workspace = f"stem: {stem}\nbranch: {stem}\nrun record: tickets/{stem}/{RUN_RECORD}\n"
        rendered = spec.render({"workspace": DataBlock("engine", workspace),
                                "ticket": DataBlock("host", _path(stem).read_text()),
                                "context": DataBlock("host", context)}, plan=plan,
                               plan_sections=ticket.plan_sections, effort="max")
        assert len(rendered) <= RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM
