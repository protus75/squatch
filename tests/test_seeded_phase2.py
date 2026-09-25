"""The Phase 2 seed enumeration test (SQUATCH_PLAN.md sections 13, 18, 19).

Pins IDENTITY and STRUCTURE of the conductor-authored Phase 2 queue: the
closed stem list, intake-lint validity, the authored frontmatter, the
`depends` edges that realize section 19's deliverable order, the drain
envelope, and the section 19 mechanical fence-read closure. Never prose
bytes, criteria counts, or live-queue state: a later `rejected` stamp is
lifecycle history, and every rendered material here is a pinned fixture.
"""

from pathlib import Path

import pytest

from squatch.config import load
from squatch.specs import DATA_MARKER, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, cycle_through, lint_ticket

REPO = Path(__file__).resolve().parent.parent

# The closed Phase 2 seed set with its DIRECT `depends` edges: the section 19
# deliverable order as the conductor's four batches (prompts 14-17) realized
# it. Later phases' seeds carry `source: seed` too, so this file never scans.
PHASE2: dict[str, tuple[str, ...]] = {
    # batch 1: caps + auto-harvest
    "spine-caps": (),
    "spine-harvest": ("spine-caps",),
    # batch 2: diagnosis + its eval
    "spine-diagnosis": ("spine-harvest",),
    "diagnosis-eval-harness": ("spine-diagnosis",),
    "diagnosis-eval-run": ("diagnosis-eval-harness",),
    # batch 3: Suggestion Box + ladder + triage
    "suggestion-box": ("spine-diagnosis",),
    "reject-verbs": ("suggestion-box",),
    "reject-queue": ("reject-verbs", "diagnosis-eval-run"),
    "escalation-ladder": ("reject-queue",),
    "box-triage": ("escalation-ladder",),
    # batch 4: Author + requisition_review + attribution + auditor + battery + exit
    "author-stage": ("box-triage",),
    "requisition-review-call": ("author-stage",),
    "requisition-review-author": ("requisition-review-call",),
    "requisition-review-seed": ("requisition-review-author",),
    "verification-attribution": ("suggestion-box",),
    "invariant-auditor": ("requisition-review-seed",),
    "shakeout-report": ("invariant-auditor",),
    "shakeout-tickets": ("shakeout-report",),
    "shakeout-stages": ("shakeout-tickets", "verification-attribution"),
    "shakeout-driver": ("shakeout-stages",),
    "shakeout-reconcile": ("shakeout-driver",),
    "shakeout-merge": ("shakeout-reconcile",),
    "shakeout-providers": ("shakeout-merge",),
    "shakeout-drain": ("shakeout-providers",),
    "shakeout-ladder": ("shakeout-drain",),
    "phase2-exit": ("shakeout-ladder",),
}
EXIT = "phase2-exit"

# Section 19's known-hard pin: the plan names the requisition_review unit and
# every phase-exit seed known-hard, so they start high/high with plan section
# 19 as the cited evidence. Every other code-bearing seed runs at the HIGH
# tier under the pre-ladder rule, effort at the default.
KNOWN_HARD = frozenset({"requisition-review-call", "requisition-review-author",
                        "requisition-review-seed", EXIT})
EVIDENCE_SECTION = "19"

# Section 19 fence-read closure: every fence entry naming a file that EXISTED
# when the seeds were authored also appears in `Context`; files a seed
# creates are exempt (Context paths must exist). A pinned fixture of the
# authoring-time tree, never a live listing -- modules the seeds create must
# not redden this later. The value is each file's char count at authoring:
# the PINNED MATERIAL the render-feasibility pin below measures, so a module
# growing later never reddens a seed it does not name.
EXISTING_AT_AUTHORING: dict[str, int] = {
    "bootstrap/conductor.py": 22840, "bootstrap/suggestions.md": 105371, "config.yaml": 3106,
    "eval/__init__.py": 81, "eval/fixtures/logic-inverted-guard-add-invoice/expected.json": 475,
    "eval/harness.py": 19717, "pyproject.toml": 530,
    "specs/implement.md": 5320, "specs/review.md": 4635, "squatch/__init__.py": 138,
    "squatch/__main__.py": 7765, "squatch/artifacts.py": 3586, "squatch/config.py": 9978,
    "squatch/drain.py": 19189, "squatch/driver.py": 8981, "squatch/effects.py": 4981,
    "squatch/enginelog.py": 2377, "squatch/gates.py": 5504, "squatch/git.py": 5368,
    "squatch/journal.py": 6660, "squatch/llm.py": 3905, "squatch/llmeffect.py": 3464,
    "squatch/lockfile.py": 3782, "squatch/merge.py": 15173, "squatch/providers.py": 14376,
    "squatch/reconcile.py": 3522, "squatch/redact.py": 2399, "squatch/runner.py": 11111,
    "squatch/seams.py": 4521, "squatch/specs.py": 16007, "squatch/stages.py": 31488,
    "squatch/status.py": 5649, "squatch/tickets.py": 36871, "tests/test_cli.py": 15174,
    "tests/test_config.py": 11684, "tests/test_drain.py": 17136,
    "tests/test_drain_reentry.py": 11060, "tests/test_drain_upgrade.py": 13169,
    "tests/test_driver.py": 22226, "tests/test_echo_stage.py": 8364, "tests/test_effects.py": 9806,
    "tests/test_eval_harness.py": 18140, "tests/test_fault_injection.py": 12260,
    "tests/test_gates.py": 9462, "tests/test_git.py": 12059, "tests/test_journal.py": 8355,
    "tests/test_llm_effect.py": 16575, "tests/test_lockfile.py": 7561, "tests/test_merge.py": 16594,
    "tests/test_providers.py": 25258, "tests/test_reconcile.py": 9109, "tests/test_scaffold.py": 1143,
    "tests/test_seams.py": 4442, "tests/test_seeded_phase2.py": 10293, "tests/test_specs.py": 15875,
    "tests/test_stages.py": 31648, "tests/test_terminal.py": 14783, "tests/test_tickets.py": 20100,
}
# Files the production Implement render refuses as Context: any carrying the
# engine's data-block delimiter (the section 8 render contract), plus the
# prompt specs the Context grammar refuses. Derived from the real rule over
# the authoring-time tree, never hand-listed: a hand list mirrors the
# author's belief and goes green over a seed the engine parks.
CONTEXT_REFUSED = frozenset(
    p for p in EXISTING_AT_AUTHORING
    if p.startswith("specs/") or not (REPO / p).is_file()
    or DATA_MARKER in (REPO / p).read_text())


def _path(stem: str) -> Path:
    return REPO / TICKETS_DIR / stem / TICKET_FILE


def _resolve(stem: str) -> bool:
    return _path(stem).is_file()


@pytest.fixture(scope="module")
def plan() -> str:
    return (REPO / PLAN_FILE).read_text()


@pytest.fixture(scope="module")
def tickets(plan):
    return {stem: lint_ticket(_path(stem).read_text(), stem=stem, repo=REPO, plan=plan,
                              resolve_stem=_resolve)
            for stem in PHASE2}


def test_every_seed_dir_exists():
    missing = [stem for stem in PHASE2 if not _path(stem).is_file()]
    assert missing == []


def test_every_seed_passes_intake_lint(plan):
    # lint_ticket raises TicketLintError naming every defect; one stem per
    # failure so a red names the seed.
    for stem in PHASE2:
        lint_ticket(_path(stem).read_text(), stem=stem, repo=REPO, plan=plan,
                    resolve_stem=_resolve)


def test_authored_state_and_source(tickets):
    for stem, t in tickets.items():
        assert t.source == "seed", stem
        # Born `confirmed`; a later Reject-queue kill stamps `rejected`, which
        # is history, not drift (section 13).
        assert t.state in {"confirmed", "rejected"}, stem
        assert t.priority == "P1", stem
        assert t.plan_sections, stem


def test_tier_pins(tickets):
    for stem, t in tickets.items():
        assert t.agent_tier == "high", stem
        if stem in KNOWN_HARD:
            assert t.agent_effort == "high", stem
            assert EVIDENCE_SECTION in t.plan_sections, stem
        else:
            assert t.agent_effort == "medium", stem


def test_stuck_budget_under_drain_envelope(tickets):
    config = load(REPO / "config.yaml", cwd=REPO)
    limit = config.drain.max_ticket_minutes
    for stem, t in tickets.items():
        assert 0 < t.expected_minutes < t.stuck_minutes, stem
        assert t.stuck_minutes <= limit, (stem, t.stuck_minutes, limit)


def test_depends_edges_realize_the_deliverable_order(tickets):
    for stem, t in tickets.items():
        assert set(t.depends) == set(PHASE2[stem]), stem
        assert all(d in PHASE2 for d in t.depends), stem


def test_seed_graph_is_acyclic():
    for stem in PHASE2:
        assert cycle_through(stem, PHASE2) is None, stem


def test_exit_transitively_covers_every_seed():
    seen: set[str] = set()
    frontier = [EXIT]
    while frontier:
        stem = frontier.pop()
        for d in PHASE2[stem]:
            if d not in seen:
                seen.add(d)
                frontier.append(d)
    assert seen == set(PHASE2) - {EXIT}


def test_fence_read_closure(tickets):
    gaps = []
    for stem, t in tickets.items():
        for entry in t.scope_fence:
            if entry.endswith("/") or entry not in EXISTING_AT_AUTHORING:
                continue  # a prefix, or a file the seed creates
            if entry in CONTEXT_REFUSED:
                continue
            if entry not in t.context:
                gaps.append((stem, entry))
    assert gaps == []


def test_context_refuses_governed_engine_prose(tickets):
    for stem, t in tickets.items():
        for entry in t.context:
            assert entry not in CONTEXT_REFUSED, (stem, entry)
            assert entry != PLAN_FILE, stem


def test_every_seed_renders_under_the_implement_bound(tickets, plan):
    # Section 19: a seed is proven BUILDABLE where authored. The production
    # first-attempt render (`Stages._implement`: workspace, ticket, Context,
    # the cited plan sections, the spec's own effort) must clear the section
    # 8 bound, else the drain parks the stem `premise_failed` before any
    # call. Context bytes are the pinned authoring-time sizes, never live
    # files (PINNED MATERIAL); the ticket and plan are the seed itself.
    spec = load_spec(REPO / "specs" / "implement.md")
    for stem, t in tickets.items():
        workspace = f"stem: {stem}\nbranch: {stem}\nrun record: {TICKETS_DIR}/{stem}/{RUN_RECORD}\n"
        context = "".join(f"### {p}\n{'x' * EXISTING_AT_AUTHORING[p]}\n" for p in t.context)
        blocks = {
            "workspace": DataBlock("engine", workspace),
            "ticket": DataBlock("host", _path(stem).read_text()),
            "context": DataBlock("host", context or "(no Context files)\n"),
        }
        spec.render(blocks, plan=plan, plan_sections=t.plan_sections)  # raises RenderRefused
