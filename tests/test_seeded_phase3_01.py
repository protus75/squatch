"""The first Phase 3 continuation seed batch (SQUATCH_PLAN.md section 20)."""

from pathlib import Path

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket

REPO = Path(__file__).resolve().parent.parent
PHASE3_01 = {
    "merge-queue": ("phase3-continue",),
    "phase3-continue-02": ("merge-queue",),
}
FENCES = {
    "merge-queue": (
        "squatch/mergequeue.py", "squatch/merge.py", "squatch/git.py", "tests/test_mergequeue.py"),
    "phase3-continue-02": ("tickets", "tests/test_seeded_phase3_02.py"),
}
EXISTING_AT_AUTHORING = {
    "config.yaml": 3106,
    "squatch/config.py": 10110,
    "squatch/git.py": 6491,
    "squatch/merge.py": 19735,
    "squatch/tickets.py": 38775,
    "tests/test_seeded_phase3_core.py": 5877,
}
AUTHORING_TEST_PATHS = (
    "tests/test_audit.py", "tests/test_author.py", "tests/test_box.py", "tests/test_caps.py",
    "tests/test_cli.py", "tests/test_config.py", "tests/test_diagnose.py", "tests/test_drain.py",
    "tests/test_drain_reentry.py", "tests/test_drain_upgrade.py", "tests/test_driver.py",
    "tests/test_echo_stage.py", "tests/test_effects.py", "tests/test_eval_diagnose.py",
    "tests/test_eval_harness.py", "tests/test_fault_injection.py", "tests/test_gates.py",
    "tests/test_git.py", "tests/test_harvest.py", "tests/test_journal.py", "tests/test_ladder.py",
    "tests/test_llm_effect.py", "tests/test_lockfile.py", "tests/test_merge.py",
    "tests/test_phase2_exit.py", "tests/test_policy.py", "tests/test_providers.py",
    "tests/test_reconcile.py", "tests/test_registry.py", "tests/test_reject.py",
    "tests/test_requisition.py", "tests/test_scaffold.py", "tests/test_scheduler.py",
    "tests/test_seams.py", "tests/test_seed_successor.py", "tests/test_seeded_phase2.py",
    "tests/test_seeded_phase3_core.py", "tests/test_seeds.py", "tests/test_shakeout.py",
    "tests/test_specs.py", "tests/test_stages.py", "tests/test_terminal.py", "tests/test_tickets.py",
    "tests/test_triage.py", "tests/test_verbs.py",
)
SUFFIX = (
    ("rework-stage",), ("thresh-runtime",),
    ("dispatch-admission-boundary", "dispatch-config-snapshot"), ("scheduler-activation",),
    ("merge-queue-activation", "rework-activation"), ("background-consumers", "control-inbox"),
    ("dispatch-pause-boundary", "pause-resume-activation"),
    ("kill-signal-journal", "kill-executor-abort"), ("kill-worker-stop", "kill-failure-suppression"),
    ("kill-cli-activation",), ("heartbeat",), ("restart-timers",),
    ("flake-detection", "flake-release"), ("journal-roll", "storm-ledger"),
    ("storm-producer-wiring", "storm-notification-activation"), ("storm-dispatch-hold",),
    ("checkpoint-push",), ("daemon-soak",), ("soak-run",), ("phase3-exit",),
)


def _path(stem):
    return REPO / TICKETS_DIR / stem / TICKET_FILE


def _text(stem):
    return _path(stem).read_text()


def _ticket(stem):
    return lint_ticket(_text(stem), stem=stem, repo=REPO, plan=(REPO / PLAN_FILE).read_text(),
                       resolve_stem=lambda candidate: _path(candidate).is_file())


def _yaml_after(text, marker):
    start = text.index(marker)
    start = text.index("```yaml", start) + len("```yaml")
    end = text.index("```", start)
    return yaml.safe_load(text[start:end])


def test_batch_is_exact_linted_and_capped():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert tuple(PHASE3_01) == ("merge-queue", "phase3-continue-02")
    assert len(PHASE3_01) <= config.seeding.max_seeds_per_admission
    for stem, depends in PHASE3_01.items():
        ticket = _ticket(stem)
        assert ticket.source == "seed"
        assert ticket.state == "confirmed"
        assert ticket.plan_sections == ("20",)
        assert ticket.depends == depends
        assert 0 < ticket.expected_minutes < ticket.stuck_minutes <= config.drain.max_ticket_minutes


def test_tiers_fences_and_finite_suffix_are_pinned():
    assert (_ticket("merge-queue").agent_tier, _ticket("merge-queue").agent_effort) == ("high", "high")
    assert (_ticket("phase3-continue-02").agent_tier,
            _ticket("phase3-continue-02").agent_effort) == ("medium", "medium")
    for stem, fence in FENCES.items():
        assert _ticket(stem).scope_fence == fence
    assert tuple(tuple(group) for group in _yaml_after(
        _text("phase3-continue-02"), "The finite ordered admissions this continuation carries are:")) == SUFFIX


def test_context_closure_and_mergequeue_ownership_are_pinned():
    for stem in PHASE3_01:
        ticket = _ticket(stem)
        assert set(ticket.context) <= set(EXISTING_AT_AUTHORING)
        for entry in ticket.context:
            assert (REPO / entry).is_file()
        for entry in ticket.scope_fence:
            if entry in EXISTING_AT_AUTHORING:
                assert entry in ticket.context
    ownership = _yaml_after(_text("merge-queue"), "## Scope in")["ownership"]["merge-queue"]
    assert ownership["owns"] == ["squatch/mergequeue.py", "tests/test_mergequeue.py"]
    assert "dormant serial admission" in ownership["contract"]


def test_mergequeue_additions_are_additive_and_predecessor_tests_are_closed():
    text = _text("merge-queue")
    assert "compose_merge_queue" in text
    for operation in ("rebase_stop_at_conflict", "conflicted_paths", "rebase_continue"):
        assert operation in text
    assert "leaving `rebase` and `rebase_abort` unchanged" in text
    assert "Do not change tested existing behavior" in text
    assert all("compose_merge_queue" not in (REPO / path).read_text()
               for path in AUTHORING_TEST_PATHS)


def test_every_seed_render_fits_requisition_headroom_with_pinned_context():
    spec = load_spec(REPO / "specs" / "implement.md")
    plan = (REPO / PLAN_FILE).read_text()
    limit = int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
    for stem in PHASE3_01:
        ticket = _ticket(stem)
        workspace = f"stem: {stem}\nbranch: {stem}\nrun record: {TICKETS_DIR}/{stem}/{RUN_RECORD}\n"
        context = "".join(f"### {path}\n{'x' * EXISTING_AT_AUTHORING[path]}\n"
                          for path in ticket.context)
        rendered = spec.render({
            "workspace": DataBlock("engine", workspace),
            "ticket": DataBlock("host", _text(stem)),
            "context": DataBlock("host", context or "(no Context files)\n"),
        }, plan=plan, plan_sections=ticket.plan_sections, effort="max")
        assert len(rendered) <= limit, (stem, len(rendered), limit)
