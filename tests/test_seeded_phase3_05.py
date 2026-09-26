"""Scheduler activation seeds and the next finite Phase 3 admission."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket

REPO = Path(__file__).resolve().parent.parent
PHASE3_05 = {
    "scheduler-activation": ("phase3-continue-05",),
    "phase3-continue-06": ("scheduler-activation",),
}
FENCES = {
    "scheduler-activation": (
        "squatch/daemon.py", "squatch/scheduler.py", "squatch/watcher.py",
        "squatch/__main__.py", "tests/test_scheduler.py", "tests/test_daemon_admission.py",
        "tests/test_daemon_composition.py",
    ),
    "phase3-continue-06": ("tickets", "tests/test_seeded_phase3_06.py"),
}
CONTEXT = {
    "scheduler-activation": (
        "squatch/config.py", "squatch/daemon.py", "squatch/scheduler.py",
        "squatch/watcher.py", "squatch/__main__.py", "tests/test_scheduler.py",
        "tests/test_daemon_admission.py", "tests/test_daemon_config.py",
    ),
    "phase3-continue-06": (
        "tests/test_seeded_phase3_04.py", "squatch/config.py",
        "tests/test_daemon_admission.py", "tests/test_daemon_config.py",
        "tests/test_mergequeue.py", "tests/test_rework.py",
    ),
}
OWNERSHIP = {
    "scheduler-activation": {
        "owns": ["tests/test_daemon_composition.py"],
        "hooks": ["squatch/daemon.py", "squatch/scheduler.py", "squatch/watcher.py",
                  "squatch/__main__.py", "tests/test_scheduler.py",
                  "tests/test_daemon_admission.py"],
    },
    "phase3-continue-06": {
        "owns": ["tickets", "tests/test_seeded_phase3_06.py"], "hooks": [],
    },
}

# Verified against main when these seeds were authored. These are synthetic
# render inputs, not assertions about files after later owner tickets merge.
EXISTING_AT_AUTHORING = {
    "tests/test_seeded_phase3_04.py": 11063,
    "squatch/config.py": 10260,
    "squatch/daemon.py": 2004,
    "squatch/scheduler.py": 1899,
    "squatch/watcher.py": 537,
    "squatch/__main__.py": 10340,
    "tests/test_scheduler.py": 4261,
    "tests/test_daemon_admission.py": 5837,
    "tests/test_daemon_config.py": 5062,
    "tests/test_mergequeue.py": 24597,
    "tests/test_rework.py": 10353,
}
SUFFIX = (
    ("merge-queue-activation", "rework-activation"),
    ("background-consumers", "control-inbox"),
    ("dispatch-pause-boundary", "pause-resume-activation"),
    ("kill-signal-journal", "kill-executor-abort"),
    ("kill-worker-stop", "kill-failure-suppression"),
    ("kill-cli-activation",), ("heartbeat",), ("restart-timers",),
    ("flake-detection", "flake-release"), ("journal-roll", "storm-ledger"),
    ("storm-producer-wiring", "storm-notification-activation"),
    ("storm-dispatch-hold",), ("checkpoint-push",), ("daemon-soak",),
    ("soak-run",), ("phase3-exit",),
)


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


def _yaml_blocks(stem):
    return [yaml.safe_load(block) for block in re.findall(
        r"```yaml\n(.*?)\n```", _section(stem, "Scope in"), re.S)]


def test_emitted_batch_is_exact_linted_and_capped():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert tuple(PHASE3_05) == ("scheduler-activation", "phase3-continue-06")
    assert len(PHASE3_05) <= config.seeding.max_seeds_per_admission
    for stem, depends in PHASE3_05.items():
        ticket = _ticket(stem)
        assert (ticket.source, ticket.state, ticket.plan_sections) == ("seed", "confirmed", ("20",))
        assert ticket.depends == depends


def test_tiers_budgets_fences_and_keyed_ownership_are_exact():
    config = load(REPO / "config.yaml", cwd=REPO)
    expected = {"scheduler-activation": ("high", "high", 120, 180),
                "phase3-continue-06": ("medium", "medium", 75, 150)}
    for stem, values in expected.items():
        ticket = _ticket(stem)
        assert (ticket.agent_tier, ticket.agent_effort, ticket.expected_minutes,
                ticket.stuck_minutes) == values
        assert 0 < ticket.expected_minutes < ticket.stuck_minutes <= config.drain.max_ticket_minutes
        assert ticket.scope_fence == FENCES[stem]
    assert _yaml_blocks("scheduler-activation") == [{"ownership": {
        "scheduler-activation": OWNERSHIP["scheduler-activation"]}}]
    assert _yaml_blocks("phase3-continue-06")[0] == {"ownership": {
            "merge-queue-activation": {
                "owns": [],
                "hooks": ["squatch/merge.py", "tests/test_mergequeue.py",
                          "tests/test_daemon_composition.py"],
        },
        "rework-activation": {
            "owns": [],
            "hooks": ["squatch/daemon.py", "squatch/rework.py", "squatch/mergequeue.py",
                      "tests/test_rework.py", "tests/test_daemon_composition.py"],
        },
        "phase3-continue-07": {
            "owns": ["tickets", "tests/test_seeded_phase3_07.py"], "hooks": [],
        },
    }}


def test_pinned_context_closure_and_predecessor_test_contracts():
    for stem, context in CONTEXT.items():
        ticket = _ticket(stem)
        assert ticket.context == context
        assert set(ticket.context) <= set(EXISTING_AT_AUTHORING)
        for entry in ticket.scope_fence:
            if entry in EXISTING_AT_AUTHORING:
                assert entry in ticket.context
    assert "tests/test_daemon_composition.py" not in EXISTING_AT_AUTHORING
    activation = _path("scheduler-activation").read_text()
    assert "compose_daemon_dispatch" in activation
    assert "call it from `squatch/__main__.py`" in activation
    assert "do not add a CLI verb" in activation
    assert "test_scheduler_and_watcher_are_unreachable_from_the_production_root" in activation
    assert "positive assertion that `squatch.daemon` is in `_local_import_closure`" in activation
    assert "test_dormancy_scan_recognizes_import_forms_and_fixture_daemon_edge" in activation
    assert "`_assert_daemon_unreachable`" in activation
    assert "local dispatch contracts in `tests/test_daemon_admission.py` and `tests/test_daemon_config.py`" in activation


def test_successor_contract_carries_compact_context_and_both_migrations():
    successor = _path("phase3-continue-06").read_text()
    assert "squatch/specs.py" not in _section("phase3-continue-06", "Context")
    assert "tests/test_daemon_composition.py" not in _section("phase3-continue-06", "Context")
    assert "then-existing composition harness" in successor
    assert "test_additive_composition_hook_does_not_change_phase1_composition" in successor
    assert 'not hasattr(pipeline, "merge_queue")' in successor
    assert "test_mergequeue_has_no_scheduler_or_watcher_dependency" in successor
    assert "test_rework_remains_unreachable_from_the_production_root" in successor
    assert "outside the `squatch.__main__` import closure" in successor
    assert "`specs/rework.md` is neither fenced nor Context" in successor
    assert "lists `tests/test_daemon_composition.py` as existing" in successor
    assert "only `tests/test_seeded_phase3_07.py` as new" in successor
    assert "not-yet-existing composition harness" not in successor


def test_continuation_carries_the_exact_shrinking_suffix():
    blocks = _yaml_blocks("phase3-continue-06")
    assert tuple(tuple(group) for group in blocks[1]) == SUFFIX
    assert tuple(tuple(group) for group in blocks[2]) == SUFFIX[1:]
    assert "scheduler-activation" not in {stem for group in SUFFIX for stem in group}


def test_every_seed_render_fits_requisition_headroom_with_pinned_context():
    spec = load_spec(REPO / "specs" / "implement.md")
    plan = (REPO / PLAN_FILE).read_text()
    limit = int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
    for stem in PHASE3_05:
        ticket = _ticket(stem)
        workspace = f"stem: {stem}\nbranch: {stem}\nrun record: {TICKETS_DIR}/{stem}/{RUN_RECORD}\n"
        context = "".join(f"### {path}\n{'x' * EXISTING_AT_AUTHORING[path]}\n"
                          for path in ticket.context)
        rendered = spec.render({
            "workspace": DataBlock("engine", workspace),
            "ticket": DataBlock("host", _path(stem).read_text()),
            "context": DataBlock("host", context or "(no Context files)\n"),
        }, plan=plan, plan_sections=ticket.plan_sections, effort="max")
        assert len(rendered) <= limit, (stem, len(rendered), limit)
