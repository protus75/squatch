"""Terminal Phase 6 admission and its compact render contract."""

from pathlib import Path
import re

import yaml

from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket


REPO = Path(__file__).resolve().parent.parent
STEM = "phase6-exit"
FENCE = (
    "tickets/phase6-exit/host-loop-report.json",
    "tickets/phase6-exit/exit-receipt.json",
    "tests/test_phase6_exit.py",
)
CONTEXT = ("squatch/artifacts.py", "tickets/go-grade-run/review-baseline-report.json")
ON_DEMAND = ("eval/host_loop.py", "squatch/stages.py")


def _path(stem=STEM):
    return REPO / TICKETS_DIR / stem / TICKET_FILE


def _ticket():
    return lint_ticket(_path().read_text(), stem=STEM, repo=REPO,
                       plan=(REPO / "tests/fixtures/squatch_plan_v1.md").read_text(),
                       resolve_stem=lambda candidate: _path(candidate).is_file())


def _scope():
    lines = _path().read_text().splitlines()
    start = lines.index("## Scope in") + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


def _admissions(stem):
    lines = _path(stem).read_text().splitlines()
    start = lines.index("## Scope in") + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    scope = "\n".join(lines[start:end])
    [rows] = [yaml.safe_load(block) for block in re.findall(r"```yaml\n(.*?)\n```", scope, re.S)
              if isinstance(yaml.safe_load(block), list)]
    return tuple(tuple(row) for row in rows)


def test_terminal_exit_identity_fence_context_and_custody():
    ticket = _ticket()
    assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
    assert ticket.depends == ("exit-receipt-machinery",)
    assert ticket.scope_fence == FENCE
    assert ticket.context == CONTEXT and ticket.plan_sections == ("20",)
    assert (ticket.agent_tier, ticket.agent_effort) == ("high", "high")
    assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
    assert all((REPO / path).is_file() for path in CONTEXT + ON_DEMAND)
    assert _admissions("phase6-continue-08") == ((STEM,),)

    scope = _scope()
    assert all(phrase in scope for phrase in (
        "terminal last-row sole KNOWN-HARD high/high", "transitively depends on every Phase 6 payload",
        "authors no successor", "`HostLoopReport`", "returned", "exit Implement",
        "`KNOWN_ARTIFACTS[HOST_LOOP_REPORT]`", "`KNOWN_ARTIFACTS[EXIT_RECEIPT]`",
        "validators, not writers", "`go-grade-machinery` owns", "`go-grade-run` produced",
        "`ReviewBaselineReport`", "`REVIEW_BASELINE_REPORT`",
        "report is incomplete, cannot record GO", "`NO_GO` without reading a journal signal",
        "Only a complete report", "latest matching current-build",
        "`review_baseline` signal", "`GO` maps to receipt enum `GO`",
        "`NO-GO` maps to", "absent or mismatched identity", "complete-report",
        "at least three",
        "distinct-run `machine_ticket_merge` entries",
        "`report_to_regression_bug_loop`", "`escape_attribution`",
        "lowercase SHA-256", "exact schema-validated", "host-loop report bytes",
        "Live-host K>=10", "real-host bug-loop evidence", "forbidden exit inputs",
    ))
    partition = scope.split("`phase6-exit` partition: Embedded Context: ", 1)[1]
    embedded, measured = partition.split("; measured on-demand:\n", 1)
    assert tuple(re.findall(r"`([^`]+)`", embedded)) == CONTEXT
    assert tuple(re.findall(r"`([^`]+)`", measured.split("\n\n", 1)[0])) == ON_DEMAND
    continuation = _path("phase6-continue-08").read_text()
    assert "The terminal row contains `phase6-exit` alone, has no successor" in continuation
    assert "continuation tail." in continuation and "phase6-continue-09" not in continuation


def test_terminal_exit_renders_at_max_effort_from_section_twenty_only():
    ticket = _ticket()
    spec = load_spec(REPO / "specs" / "implement.md")
    context = "".join(f"### {path}\n{(REPO / path).read_text()}\n" for path in ticket.context)
    rendered = spec.render({
        "workspace": DataBlock("engine", f"stem: {STEM}\nbranch: {STEM}\n"
                               f"run record: tickets/{STEM}/{RUN_RECORD}\n"),
        "ticket": DataBlock("host", _path().read_text()),
        "context": DataBlock("host", context),
    }, plan=(REPO / "tests/fixtures/squatch_plan_v1.md").read_text(), plan_sections=ticket.plan_sections, effort="max")
    assert ticket.plan_sections == ("20",)
    assert "## 19. Implementation phases" not in rendered
    assert "Phase 5/6 compact-render correction (DECIDED" in rendered
    assert "Phase 6 remaining-row contracts (DECIDED)" in rendered
    assert len(rendered) <= int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
