"""The Phase 3 core seed batch (SQUATCH_PLAN.md sections 19 and 20).

Pins identity and structure only. Seed prose remains review-owned, and a later
Reject-queue stamp is lifecycle history rather than seed drift.
"""

from pathlib import Path

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket

REPO = Path(__file__).resolve().parent.parent

PHASE3_CORE: dict[str, tuple[str, ...]] = {
    "daemon-scheduler": ("phase2-exit",),
    "seed-successor-proof": ("phase2-exit",),
    "phase3-continue": ("phase2-exit", "daemon-scheduler", "seed-successor-proof"),
}

OWNER_FENCES = {
    "daemon-scheduler": (
        "squatch/scheduler.py",
        "squatch/watcher.py",
        "tests/test_scheduler.py",
    ),
    "seed-successor-proof": ("tests/test_seed_successor.py",),
    "phase3-continue": ("tickets", "tests/test_seeded_phase3_01.py"),
}

# Pinned material from main when this batch was authored. New owner files are
# intentionally absent: Context accepts only files that already exist.
EXISTING_AT_AUTHORING: dict[str, int] = {
    "config.yaml": 3106,
    "eval/shakeout/bench.py": 7916,
    "squatch/__main__.py": 10340,
    "squatch/config.py": 10110,
    "squatch/git.py": 6491,
    "squatch/merge.py": 19735,
    "squatch/seeds.py": 7330,
    "squatch/tickets.py": 38775,
    "tests/test_seeded_phase2.py": 10325,
    "tests/test_seeds.py": 6447,
    "tests/test_terminal.py": 43668,
}
PLAN_SECTION_AT_AUTHORING = 8704

# One tuple per future admission; successor-seeder tails are structural and
# therefore are not repeated in this shrinking deliverable partition.
PHASE3_REMAINDER = (
    ("merge-queue",),
    ("rework-stage",),
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


def _path(stem: str) -> Path:
    return REPO / TICKETS_DIR / stem / TICKET_FILE


def _resolve(stem: str) -> bool:
    return _path(stem).is_file()


def _ticket(stem: str):
    plan = (REPO / PLAN_FILE).read_text()
    return lint_ticket(_path(stem).read_text(), stem=stem, repo=REPO, plan=plan,
                       resolve_stem=_resolve)


def _structured_scope_in(stem: str):
    lines = _path(stem).read_text().splitlines()
    start = lines.index("## Scope in") + 1
    end = next(i for i in range(start, len(lines)) if lines[i].startswith("## "))
    section = lines[start:end]
    first = section.index("```yaml") + 1
    last = section.index("```", first)
    return tuple(tuple(group) for group in yaml.safe_load("\n".join(section[first:last])))


def test_core_batch_is_exact_and_within_the_admission_cap():
    assert tuple(PHASE3_CORE) == (
        "daemon-scheduler", "seed-successor-proof", "phase3-continue")
    config = load(REPO / "config.yaml", cwd=REPO)
    assert len(PHASE3_CORE) <= config.seeding.max_seeds_per_admission
    assert all(_path(stem).is_file() for stem in PHASE3_CORE)


def test_core_seeds_lint_and_pin_authored_fields():
    config = load(REPO / "config.yaml", cwd=REPO)
    for stem, depends in PHASE3_CORE.items():
        ticket = _ticket(stem)
        assert ticket.source == "seed", stem
        assert ticket.state in {"confirmed", "rejected"}, stem
        assert ticket.priority == "P1", stem
        assert (ticket.agent_tier, ticket.agent_effort) == ("medium", "medium"), stem
        assert ticket.depends == depends, stem
        assert "phase2-exit" in ticket.depends, stem
        assert ticket.plan_sections == ("20",), stem
        assert 0 < ticket.expected_minutes < ticket.stuck_minutes, stem
        assert ticket.stuck_minutes <= config.drain.max_ticket_minutes, stem


def test_owner_fences_and_authoring_time_read_closure():
    for stem, expected in OWNER_FENCES.items():
        ticket = _ticket(stem)
        assert ticket.scope_fence == expected, stem
        assert set(ticket.context) <= set(EXISTING_AT_AUTHORING), stem
        for entry in ticket.scope_fence:
            if entry in EXISTING_AT_AUTHORING:
                assert entry in ticket.context, (stem, entry)


def test_continuation_carries_the_finite_ordered_remainder():
    assert _structured_scope_in("phase3-continue") == PHASE3_REMAINDER


def test_every_seed_render_fits_authoring_headroom_with_pinned_context():
    spec = load_spec(REPO / "specs" / "implement.md")
    plan = (REPO / PLAN_FILE).read_text()
    start = plan.index("## 20.")
    body = plan.index("\n", start) + 1
    end = plan.index("\n## ", body) + 1
    plan = plan[:body] + "x" * (PLAN_SECTION_AT_AUTHORING - 1) + "\n" + plan[end:]
    limit = int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
    for stem in PHASE3_CORE:
        ticket = _ticket(stem)
        workspace = (f"stem: {stem}\nbranch: {stem}\n"
                     f"run record: {TICKETS_DIR}/{stem}/{RUN_RECORD}\n")
        context = "".join(
            f"### {path}\n{'x' * EXISTING_AT_AUTHORING[path]}\n"
            for path in ticket.context)
        rendered = spec.render({
            "workspace": DataBlock("engine", workspace),
            "ticket": DataBlock("host", _path(stem).read_text()),
            "context": DataBlock("host", context or "(no Context files)\n"),
        }, plan=plan, plan_sections=ticket.plan_sections, effort="max")
        assert len(rendered) <= limit, (stem, len(rendered), limit)
