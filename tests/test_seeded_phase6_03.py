"""Row 3 admission, repaired Context partitions, and the finite exit custody."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket


REPO = Path(__file__).resolve().parent.parent
ROW = ("bug-gate-grammar", "report-inbox-triage", "phase6-continue-04")
SUFFIX = (
    ROW,
    ("escape-column", "phase6-continue-05"),
    ("supervised-merge-hold", "phase6-continue-06"),
    ("go-grade-machinery", "go-grade-run", "phase6-continue-07"),
    ("exit-receipt-machinery", "phase6-continue-08"),
    ("phase6-exit",),
)
FENCES = {
    "bug-gate-grammar": (
        "squatch/tickets.py", "squatch/gates.py", "squatch/stages.py",
        "tests/test_tickets.py", "tests/test_gates.py", "tests/test_bug_gate.py"),
    "report-inbox-triage": (
        "squatch/inbox.py", "squatch/box.py", "squatch/triage.py",
        "squatch/author.py", "squatch/daemon.py", "tests/test_box.py",
        "tests/test_triage.py", "tests/test_author.py", "tests/test_inbox.py"),
    "phase6-continue-04": ("tickets", "tests/test_seeded_phase6_04.py"),
}
CONTEXT = {
    "bug-gate-grammar": ("squatch/gates.py", "tests/test_gates.py"),
    "report-inbox-triage": ("squatch/box.py", "tests/test_box.py"),
    "phase6-continue-04": ("tests/test_seeded_phase6_02.py",),
}
ON_DEMAND = {
    "bug-gate-grammar": ("squatch/tickets.py", "squatch/stages.py", "tests/test_tickets.py"),
    "report-inbox-triage": (
        "squatch/triage.py", "squatch/author.py", "squatch/daemon.py",
        "tests/test_author.py", "tests/test_triage.py"),
}
EXISTING_FENCE = {
    "bug-gate-grammar": FENCES["bug-gate-grammar"][:-1],
    "report-inbox-triage": CONTEXT["report-inbox-triage"] + ON_DEMAND["report-inbox-triage"],
}
CONTRACTS = {
    "bug-gate-grammar": (
        "`kind: bug`", "mandatory `## Regression`",
        "branch-head-pass/merge-base-with-`carries`-overlay-fail hard gate",
        "missing test at base is never accepted as defect evidence"),
    "report-inbox-triage": (
        "version-1 report schema", "metadata-first 1 MiB replay-file and 64 KiB log-excerpt caps",
        "durable Box custody", "`## Regression` survive intake"),
}


def _path(stem):
    return REPO / TICKETS_DIR / stem / TICKET_FILE


def _ticket(stem):
    return lint_ticket(_path(stem).read_text(), stem=stem, repo=REPO,
                       plan=(REPO / PLAN_FILE).read_text(),
                       resolve_stem=lambda candidate: _path(candidate).is_file())


def _scope(stem):
    lines = _path(stem).read_text().splitlines()
    start = lines.index("## Scope in") + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


def _admissions(stem):
    [rows] = [yaml.safe_load(block) for block in re.findall(r"```yaml\n(.*?)\n```", _scope(stem), re.S)
              if isinstance(yaml.safe_load(block), list)]
    return tuple(tuple(row) for row in rows)


def _paths(value):
    return tuple(re.findall(r"`([^`]+)`", value))


def test_row_three_identity_edges_tiers_fences_and_repaired_partitions():
    assert _admissions("phase6-continue-03") == SUFFIX
    assert len(ROW) <= load(REPO / "config.yaml", cwd=REPO).seeding.max_seeds_per_admission == 3
    expected = (("fixture-host-scaffold",), ("bug-gate-grammar",), ROW[:2])
    for stem, depends in zip(ROW, expected, strict=True):
        ticket = _ticket(stem)
        assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
        assert ticket.depends == depends and ticket.scope_fence == FENCES[stem]
        assert ticket.context == CONTEXT[stem] and ticket.plan_sections == ("20",)
        assert (ticket.agent_tier, ticket.agent_effort) == ("medium", "medium")
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
    for stem, phrases in CONTRACTS.items():
        scope = _scope(stem)
        assert all(phrase in scope for phrase in phrases), stem
        assert set(CONTEXT[stem]).isdisjoint(ON_DEMAND[stem])
        assert set(CONTEXT[stem]) | set(ON_DEMAND[stem]) == set(EXISTING_FENCE[stem])
    assert "tests/test_triage.py" not in CONTEXT["report-inbox-triage"]


def test_continuation_and_terminal_custody_are_closed():
    scope = _scope("phase6-continue-03")
    for stem, depends, context in (
        ("phase6-continue-04", ROW[:2], "tests/test_seeded_phase6_02.py"),
        ("phase6-continue-05", ("escape-column",), "tests/test_seeded_phase6_03.py"),
        ("phase6-continue-06", ("supervised-merge-hold",), "tests/test_seeded_phase6_04.py"),
        ("phase6-continue-07", ("go-grade-machinery", "go-grade-run"), "tests/test_seeded_phase6_05.py"),
        ("phase6-continue-08", ("exit-receipt-machinery",), "tests/test_seeded_phase6_06.py"),
    ):
        [line] = [line for line in scope.splitlines() if line.startswith(f"`{stem}` depends on ")]
        assert _paths(line) == (stem, *depends, "tickets", f"tests/test_seeded_phase6_{int(stem[-2:]):02d}.py", context)
    assert SUFFIX[-1] == ("phase6-exit",)
    assert "owns/fences only `tickets/phase6-exit/host-loop-report.json`, " \
           "`tickets/phase6-exit/exit-receipt.json`, and new `tests/test_phase6_exit.py`" in scope
    assert "The terminal row contains `phase6-exit` alone, has no successor, and authors no continuation tail." in scope
    assert "phase6-continue-09" not in scope
    assert not (REPO / TICKETS_DIR / "phase6-continue-09").exists()


def test_every_authored_seed_renders_at_max_effort_with_section_twenty_only():
    spec = load_spec(REPO / "specs" / "implement.md")
    plan = (REPO / PLAN_FILE).read_text()
    limit = int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
    for stem in ROW:
        ticket = _ticket(stem)
        context = "".join(f"### {path}\n{(REPO / path).read_text()}\n" for path in ticket.context)
        rendered = spec.render({
            "workspace": DataBlock("engine", f"stem: {stem}\nbranch: {stem}\n"
                                   f"run record: tickets/{stem}/{RUN_RECORD}\n"),
            "ticket": DataBlock("host", _path(stem).read_text()),
            "context": DataBlock("host", context),
        }, plan=plan, plan_sections=ticket.plan_sections, effort="max")
        assert ticket.plan_sections == ("20",)
        assert "## 19. Implementation phases" not in rendered
        assert len(rendered) <= limit, (stem, len(rendered), limit)
