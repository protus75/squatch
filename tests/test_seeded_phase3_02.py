"""The Rework admission and its shrinking Phase 3 continuation (section 20)."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket

REPO = Path(__file__).resolve().parent.parent
PHASE3_02 = {
    "rework-stage": ("phase3-continue-02",),
    "phase3-continue-03": ("rework-stage",),
}
FENCES = {
    "rework-stage": (
        "squatch/rework.py", "specs/rework.md", "squatch/mergequeue.py", "tests/test_rework.py",
    ),
    "phase3-continue-03": ("tickets", "tests/test_seeded_phase3_03.py"),
}
BUDGETS = {"rework-stage": (120, 180), "phase3-continue-03": (75, 150)}
TIERS = {"rework-stage": ("high", "high"), "phase3-continue-03": ("medium", "medium")}

# Authoring-time sizes are synthetic render inputs, never live-file invariants:
# later admissions own and edit several of these paths outside this test's fence.
EXISTING_AT_AUTHORING = {
    "config.yaml": 3106,
    "squatch/config.py": 10110,
    "squatch/journal.py": 7110,
    "squatch/ladder.py": 5304,
    "squatch/llm.py": 3905,
    "squatch/mergequeue.py": 12798,
    "squatch/providers.py": 15491,
    "squatch/reject.py": 3742,
    "squatch/tickets.py": 38775,
    "tests/test_mergequeue.py": 24597,
    "tests/test_providers.py": 27470,
}
SUFFIX = (
    ("thresh-runtime",),
    ("dispatch-admission-boundary", "dispatch-config-snapshot"),
    ("scheduler-activation",),
    ("merge-queue-activation", "rework-activation"),
    ("background-consumers", "control-inbox"),
    ("dispatch-pause-boundary", "pause-resume-activation"),
    ("kill-signal-journal", "kill-executor-abort"),
    ("kill-worker-stop", "kill-failure-suppression"),
    ("kill-cli-activation",),
    ("heartbeat",),
    ("restart-timers",),
    ("flake-detection", "flake-release"),
    ("journal-roll", "storm-ledger"),
    ("storm-producer-wiring", "storm-notification-activation"),
    ("storm-dispatch-hold",),
    ("checkpoint-push",),
    ("daemon-soak",),
    ("soak-run",),
    ("phase3-exit",),
)


def _path(stem):
    return REPO / TICKETS_DIR / stem / TICKET_FILE


def _ticket(stem):
    return lint_ticket(
        _path(stem).read_text(), stem=stem, repo=REPO, plan=(REPO / PLAN_FILE).read_text(),
        resolve_stem=lambda candidate: _path(candidate).is_file())


def _section(stem, name):
    lines = _path(stem).read_text().splitlines()
    start = lines.index(f"## {name}") + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


def _yaml_blocks(stem):
    section = _section(stem, "Scope in")
    return [yaml.safe_load(block) for block in re.findall(r"```yaml\n(.*?)\n```", section, re.S)]


def test_emitted_batch_is_exact_linted_and_capped():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert tuple(PHASE3_02) == ("rework-stage", "phase3-continue-03")
    assert set(re.findall(r"`tickets/([^/]+)/ticket\.md`",
                          _section("phase3-continue-02", "Scope in"))) == set(PHASE3_02)
    assert len(PHASE3_02) <= config.seeding.max_seeds_per_admission
    for stem, depends in PHASE3_02.items():
        ticket = _ticket(stem)
        assert (ticket.source, ticket.state) == ("seed", "confirmed"), stem
        assert ticket.plan_sections == ("20",), stem
        assert ticket.depends == depends, stem
        assert (ticket.agent_tier, ticket.agent_effort) == TIERS[stem], stem
        assert (ticket.expected_minutes, ticket.stuck_minutes) == BUDGETS[stem], stem
        assert 0 < ticket.expected_minutes < ticket.stuck_minutes <= config.drain.max_ticket_minutes


def test_fences_context_closure_and_keyed_ownership():
    for stem, fence in FENCES.items():
        ticket = _ticket(stem)
        assert ticket.scope_fence == fence, stem
        assert set(ticket.context) <= set(EXISTING_AT_AUTHORING), stem
        for entry in ticket.scope_fence:
            if entry in EXISTING_AT_AUTHORING:
                assert entry in ticket.context, (stem, entry)
    ownership = _yaml_blocks("rework-stage")[0]["ownership"]
    assert ownership == {"rework-stage": {
        "owns": ["squatch/rework.py", "specs/rework.md", "tests/test_rework.py"],
        "hooks": ["squatch/mergequeue.py"],
    }}
    assert {
        "squatch/mergequeue.py", "tests/test_mergequeue.py", "squatch/tickets.py",
        "squatch/ladder.py", "squatch/reject.py", "squatch/journal.py", "squatch/llm.py",
    } <= set(_ticket("rework-stage").context)


def test_rework_preserves_its_predecessor_and_verifies_its_own_boundary():
    scope_in = _section("rework-stage", "Scope in")
    scope_out = _section("rework-stage", "Scope out")
    assert "Consume `MergeQueue.next_rework()` and import `UnresolvedConflictHandoff` unchanged" in scope_in
    assert "the `squatch/mergequeue.py` hook permits no edit" in scope_in
    assert "Do not change merge-queue behavior or make merge-queue test edits" in scope_out
    criteria = _section("rework-stage", "Acceptance criteria")
    assert "`tests/test_mergequeue.py` exits 0 unedited" in criteria
    for test_file in ("tests/test_rework.py", "tests/test_mergequeue.py"):
        assert ("uv", "run", "pytest", test_file, "-q") in _ticket("rework-stage").verification
    assert ("uv", "run", "pytest", "-q") in _ticket("rework-stage").verification


def test_continuation_carries_exactly_the_shrinking_ordered_suffix():
    blocks = _yaml_blocks("phase3-continue-03")
    assert len(blocks) == 2
    assert tuple(tuple(group) for group in blocks[1]) == SUFFIX
    predecessor = _yaml_blocks("phase3-continue-02")[1]
    assert tuple(tuple(group) for group in predecessor) == (("rework-stage",), *SUFFIX)
    assert blocks[0]["ownership"] == {"thresh-runtime": {
        "owns": ["squatch/thresh.py", "tests/test_thresh.py"],
        "hooks": ["squatch/providers.py", "squatch/config.py", "tests/test_providers.py"],
    }}
    criteria = _section("phase3-continue-03", "Acceptance criteria")
    assert "rework-stage -> thresh-runtime -> phase3-continue-04" in criteria
    assert "`thresh-runtime` at high/high with expected/stuck minutes 120m/180m" in criteria
    assert "`phase3-continue-04` at medium/medium with expected/stuck minutes 75m/150m" in criteria
    assert "`squatch/thresh.py`, `squatch/providers.py`, `squatch/config.py`, `tests/test_thresh.py`, `tests/test_providers.py`" in criteria
    assert "`tickets`, `tests/test_seeded_phase3_04.py`" in criteria
    assert "`tests/test_providers.py` remains in the `thresh-runtime` fence" in criteria
    assert "`EXISTING_AT_AUTHORING`" in criteria
    assert "every existing fence path is in Context" in criteria
    assert "`drain.max_ticket_minutes`" in criteria
    assert _ticket("phase3-continue-03").verification == (
        ("uv", "run", "pytest", "tests/test_seeded_phase3_03.py", "-q"),
        ("uv", "run", "pytest", "-q"),
    )


def test_every_seed_render_fits_requisition_headroom_with_pinned_context():
    spec = load_spec(REPO / "specs" / "implement.md")
    plan = (REPO / PLAN_FILE).read_text()
    limit = int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
    for stem in PHASE3_02:
        ticket = _ticket(stem)
        workspace = f"stem: {stem}\nbranch: {stem}\nrun record: {TICKETS_DIR}/{stem}/{RUN_RECORD}\n"
        context = "".join(f"### {path}\n{'x' * EXISTING_AT_AUTHORING[path]}\n"
                          for path in ticket.context)
        rendered = spec.render({
            "workspace": DataBlock("engine", workspace),
            "ticket": DataBlock("host", _path(stem).read_text()),
            "context": DataBlock("host", context),
        }, plan=plan, plan_sections=ticket.plan_sections, effort="max")
        assert len(rendered) <= limit, (stem, len(rendered), limit)
