"""The threshold-runtime admission and its shrinking Phase 3 continuation."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket

REPO = Path(__file__).resolve().parent.parent
PHASE3_03 = {
    "thresh-runtime": ("rework-stage",),
    "phase3-continue-04": ("thresh-runtime",),
}
FENCES = {
    "thresh-runtime": (
        "squatch/thresh.py", "squatch/providers.py", "squatch/config.py",
        "tests/test_thresh.py", "tests/test_providers.py",
    ),
    "phase3-continue-04": ("tickets", "tests/test_seeded_phase3_04.py"),
}
BUDGETS = {"thresh-runtime": (120, 180), "phase3-continue-04": (75, 150)}
TIERS = {"thresh-runtime": ("high", "high"), "phase3-continue-04": ("medium", "medium")}

# Pinned authoring sizes are synthetic render inputs, not later live-file assertions.
EXISTING_AT_AUTHORING = {
    "squatch/providers.py": 15491,
    "squatch/config.py": 10110,
    "tests/test_providers.py": 27470,
    "tickets/phase3-continue-03/ticket.md": 4876,
    "tests/test_seeded_phase3_core.py": 5877,
}
PLAN_SECTION_AT_AUTHORING = 8890
SUFFIX = (
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
    assert tuple(PHASE3_03) == ("thresh-runtime", "phase3-continue-04")
    assert set(re.findall(r"`tickets/([^/]+)/ticket\.md`",
                          _section("phase3-continue-03", "Scope in"))) == set(PHASE3_03)
    assert len(PHASE3_03) <= config.seeding.max_seeds_per_admission
    for stem, depends in PHASE3_03.items():
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
    ownership = _yaml_blocks("thresh-runtime")[0]["ownership"]
    assert ownership == {"thresh-runtime": {
        "owns": ["squatch/thresh.py", "tests/test_thresh.py"],
        "hooks": ["squatch/providers.py", "squatch/config.py", "tests/test_providers.py"],
    }}
    threshold = _ticket("thresh-runtime")
    assert "tests/test_providers.py" in threshold.scope_fence
    assert set(threshold.context) == {
        "squatch/providers.py", "squatch/config.py", "tests/test_providers.py"}
    assert set(_ticket("phase3-continue-04").context) == {
        "tickets/phase3-continue-03/ticket.md", "tests/test_seeded_phase3_core.py"}


def test_continuation_carries_the_exact_ordered_suffix():
    blocks = _yaml_blocks("phase3-continue-04")
    assert len(blocks) == 2
    assert tuple(tuple(group) for group in blocks[0]) == SUFFIX
    assert tuple(tuple(group) for group in blocks[1]) == SUFFIX[1:]
    predecessor = _yaml_blocks("phase3-continue-03")[1]
    assert tuple(tuple(group) for group in predecessor) == (("thresh-runtime",), *SUFFIX)


def test_every_seed_render_fits_requisition_headroom_with_pinned_context():
    spec = load_spec(REPO / "specs" / "implement.md")
    plan = (REPO / PLAN_FILE).read_text()
    start = plan.index("## 20.")
    body = plan.index("\n", start) + 1
    end = plan.index("\n## ", body) + 1
    plan = plan[:body] + "x" * (PLAN_SECTION_AT_AUTHORING - 1) + "\n" + plan[end:]
    limit = int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
    for stem in PHASE3_03:
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
