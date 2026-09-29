"""Row 4 admission, its escape contract, and the terminal suffix."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket


REPO = Path(__file__).resolve().parent.parent
ROW = ("escape-column", "phase6-continue-05")
SUFFIX = (
    ROW,
    ("supervised-merge-hold", "phase6-continue-06"),
    ("go-grade-machinery", "go-grade-run", "phase6-continue-07"),
    ("exit-receipt-machinery", "phase6-continue-08"),
    ("phase6-exit",),
)
FENCES = {
    "escape-column": (
        "squatch/scorecard.py", "squatch/git.py", "squatch/retro.py", "squatch/__main__.py",
        "tests/test_scorecard.py", "tests/test_git.py", "tests/test_retro.py", "tests/test_cli.py",
        "tests/test_mergequeue.py"),
    "phase6-continue-05": ("tickets", "tests/test_seeded_phase6_05.py"),
}
CONTEXT = {
    "escape-column": ("squatch/scorecard.py", "tests/test_scorecard.py"),
    "phase6-continue-05": ("tests/test_seeded_phase6_03.py",),
}
ON_DEMAND = (
    "squatch/git.py", "squatch/retro.py", "squatch/__main__.py", "tests/test_git.py",
    "tests/test_retro.py", "tests/test_cli.py", "tests/test_mergequeue.py")
ESCAPE_CONTRACT = (
    "resolved `bug_report` evidence `app_commit`", "lowercase SHA or `BASE..HEAD`",
    "first-parent `HEAD` ancestry", "one valid trailer pair (`squatch-ticket`, `squatch-reviewed-sha`)",
    "immutable `(signature,ticket)`", "scorecard remains pure",
    "Count each passed-Check report/ticket/surface once",
    "exclude duplicate/fail/bypass/absent/unattributed data",
    "public-Git allowlist for this operation")
REMAINING = {
    "supervised-merge-hold": (
        "KNOWN-DEEP high/high", "durable HELD admission", "identity-bound `confirm`",
        "rebase/regates", "never holds the bootstrap self-build"),
    "go-grade-machinery": (
        "at least 50 planted defects", "USD 5.00 cap", "operator-only `--record-go`",
        "never uses production `specs/author.md`"),
    "go-grade-run": ("changes no code", "GO-or-NO-GO verdict signal identity", "NO-GO is valid"),
    "exit-receipt-machinery": (
        "closed writers for `host-loop-report.json` and `exit-receipt.json`", "supervised `serve`",
        "at least three machine-ticket merges", "report-to-regression bug loop", "escape attribution",
        "never produces terminal artifacts"),
    "phase6-exit": (
        "KNOWN-HARD high/high", "authors no successor", "accepts GO or NO-GO", "writes receipt digest",
        "forbidden exit inputs"),
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


def test_escape_row_identity_edges_tier_fence_and_partition():
    assert _admissions("phase6-continue-04") == SUFFIX
    assert len(ROW) <= load(REPO / "config.yaml", cwd=REPO).seeding.max_seeds_per_admission == 3
    for stem, depends in zip(ROW, (("bug-gate-grammar", "report-inbox-triage"), ("escape-column",)), strict=True):
        ticket = _ticket(stem)
        assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
        assert ticket.depends == depends and ticket.scope_fence == FENCES[stem]
        assert ticket.context == CONTEXT[stem] and ticket.plan_sections == ("20",)
        assert (ticket.agent_tier, ticket.agent_effort) == ("medium", "medium")
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
    scope = _scope("escape-column")
    assert all(phrase in scope for phrase in ESCAPE_CONTRACT)
    assert set(CONTEXT["escape-column"]).isdisjoint(ON_DEMAND)
    assert set(CONTEXT["escape-column"]) | set(ON_DEMAND) == set(FENCES["escape-column"])


def test_continuation_pins_remaining_contracts_and_terminal_custody():
    scope = _scope("phase6-continue-05")
    assert _admissions("phase6-continue-05") == SUFFIX[1:]
    assert "section 20 alone" in scope and "never render section 19" in scope
    assert "starts medium/medium unless KNOWN-DEEP or KNOWN-HARD high/high" in scope
    for stem, phrases in REMAINING.items():
        assert all(phrase in scope for phrase in phrases), stem
    for stem, depends, context in (
        ("phase6-continue-06", ("supervised-merge-hold",), "tests/test_seeded_phase6_04.py"),
        ("phase6-continue-07", ("go-grade-machinery", "go-grade-run"), "tests/test_seeded_phase6_05.py"),
        ("phase6-continue-08", ("exit-receipt-machinery",), "tests/test_seeded_phase6_06.py"),
    ):
        [line] = [line for line in scope.splitlines() if line.startswith(f"`{stem}` depends on ")]
        assert _paths(line) == (stem, *depends, "tickets", f"tests/test_seeded_phase6_{int(stem[-2:]):02d}.py", context)
    assert "The terminal row contains `phase6-exit` alone, has no successor, and authors no continuation tail." in scope
    assert "phase6-continue-09" not in scope and not (REPO / TICKETS_DIR / "phase6-continue-09").exists()


def test_authored_seeds_render_at_max_effort_with_section_twenty_only():
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
        assert len(rendered) <= limit, (stem, len(rendered), limit)
