"""Row 7 host-loop admission and terminal Phase 6 custody."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket


REPO = Path(__file__).resolve().parent.parent
ROW = ("exit-receipt-machinery", "phase6-continue-08")
SUFFIX = (ROW, ("phase6-exit",))
FENCES = {
    "exit-receipt-machinery": (
        "squatch/artifacts.py", "squatch/stages.py", "eval/host_loop.py",
        "tests/test_host_loop.py", "tests/test_gates.py", "tests/test_stages.py",
        "hosts/fixture/config.yaml", "hosts/fixture/bin/codex"),
    "phase6-continue-08": ("tickets", "tests/test_seeded_phase6_08.py"),
}
CONTEXT = {
    "exit-receipt-machinery": ("squatch/artifacts.py", "tests/test_gates.py"),
    "phase6-continue-08": ("tests/test_seeded_phase6_06.py",),
}
ON_DEMAND = ("squatch/stages.py", "tests/test_stages.py", "hosts/fixture/")


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


def test_host_loop_identity_tier_fence_and_partition():
    assert _admissions("phase6-continue-07") == SUFFIX
    assert len(ROW) <= load(REPO / "config.yaml", cwd=REPO).seeding.max_seeds_per_admission == 3
    for stem, depends in zip(ROW, (("go-grade-run",), ("exit-receipt-machinery",)), strict=True):
        ticket = _ticket(stem)
        assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
        assert ticket.depends == depends and ticket.scope_fence == FENCES[stem]
        assert ticket.context == CONTEXT[stem] and ticket.plan_sections == ("20",)
        assert (ticket.agent_tier, ticket.agent_effort) == ("medium", "medium")
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
    scope = _scope("exit-receipt-machinery")
    assert all(phrase in scope for phrase in (
        "closed ordinary-lane writers", "supervised `serve`",
        "control inbox", "at least\nthree machine-ticket merges",
        "report-to-regression bug loop", "escape\nattribution",
        "fixture `triage` route", "production Serve/triage path",
        "never produces terminal artifacts"))
    assert set(CONTEXT["exit-receipt-machinery"]).isdisjoint(ON_DEMAND)
    assert all(path in scope for path in ON_DEMAND)


def test_continuation_pins_terminal_exit_custody():
    scope = _scope("phase6-continue-08")
    assert _admissions("phase6-continue-08") == SUFFIX[1:]
    assert "section 20 alone" in scope and "never render section 19" in scope
    assert "KNOWN-HARD high/high" in scope
    [line] = [line for line in scope.splitlines() if line.startswith("`phase6-exit` depends on ")]
    assert tuple(re.findall(r"`([^`]+)`", line)) == ("phase6-exit", "exit-receipt-machinery")
    assert all(phrase in scope for phrase in (
        "transitively depends on", "authors no successor",
        "tickets/phase6-exit/host-loop-report.json", "tickets/phase6-exit/exit-receipt.json",
        "tests/test_phase6_exit.py", "committed GO-grade report",
        "embedded verdict identity", "latest matching `review_baseline` journal signal",
        "signal `GO` maps to receipt enum `GO`", "signal `NO-GO` maps to receipt enum `NO_GO`",
        "three closed\nhost-loop members", "exact schema-validated host-loop report bytes",
        "`squatch/stages.py` `KNOWN_ARTIFACTS`", "no engine-code edit",
        "forbidden exit inputs"))
    assert "Embedded Context: none; measured on-demand: none." in scope
    assert "The terminal row contains `phase6-exit` alone, has no successor" in scope
    assert "continuation tail." in scope
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
        assert "## 19. Implementation phases" not in rendered
        assert len(rendered) <= limit, (stem, len(rendered), limit)
