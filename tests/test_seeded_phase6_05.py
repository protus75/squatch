"""Row 5 supervised admission and the remaining terminal custody."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket


REPO = Path(__file__).resolve().parent.parent
ROW = ("supervised-merge-hold", "phase6-continue-06")
SUFFIX = (
    ROW,
    ("go-grade-machinery", "go-grade-run", "phase6-continue-07"),
    ("exit-receipt-machinery", "phase6-continue-08"),
    ("phase6-exit",),
)
FENCES = {
    "supervised-merge-hold": (
        "squatch/merge.py", "squatch/baseline.py", "squatch/control.py",
        "squatch/__main__.py", "squatch/stages.py", "squatch/drain.py",
        "squatch/runner.py", "eval/daemon_soak.py", "tests/test_merge.py", "tests/test_baseline.py",
        "tests/test_control_cli.py", "tests/test_cli.py", "tests/test_drain.py",
        "tests/test_daemon_soak_runner.py",
        "tests/test_supervised_merge_hold.py"),
    "phase6-continue-06": ("tickets", "tests/test_seeded_phase6_06.py"),
}
CONTEXT = {
    "supervised-merge-hold": (),
    "phase6-continue-06": ("tests/test_seeded_phase6_04.py",),
}
ON_DEMAND = FENCES["supervised-merge-hold"][:-1]
REMAINING = {
    "go-grade-machinery": (
        "at least 50 planted defects", "USD 5.00 cap", "operator-only `--record-go`",
        "never uses production `specs/author.md`", "review-baseline-report.json",
        "verdict-signal identity", "`review_baseline` signal", "`resolve_baseline`"),
    "go-grade-run": ("changes no code", "GO-or-NO-GO verdict signal identity", "NO-GO is valid"),
    "exit-receipt-machinery": (
        "closed writers for `host-loop-report.json` and `exit-receipt.json`", "supervised `serve`",
        "at least three machine-ticket merges", "report-to-regression bug loop", "escape attribution",
        "never produces terminal artifacts"),
    "phase6-exit": (
        "KNOWN-HARD high/high", "authors no successor", "accepts GO or NO-GO",
        "writes receipt digest", "forbidden exit inputs"),
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


def test_supervised_hold_identity_tier_fence_and_partition():
    assert _admissions("phase6-continue-05") == SUFFIX
    assert len(ROW) <= load(REPO / "config.yaml", cwd=REPO).seeding.max_seeds_per_admission == 3
    for stem, depends in zip(ROW, (("escape-column",), ("supervised-merge-hold",)), strict=True):
        ticket = _ticket(stem)
        assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
        assert ticket.depends == depends and ticket.scope_fence == FENCES[stem]
        assert ticket.context == CONTEXT[stem] and ticket.plan_sections == ("20",)
        expected_tier = ("high", "high") if stem == "supervised-merge-hold" else ("medium", "medium")
        assert (ticket.agent_tier, ticket.agent_effort) == expected_tier
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
    scope = _scope("supervised-merge-hold")
    assert all(phrase in scope for phrase in (
        "durable HELD admission", "merge safety and integration checks but before main mutation",
        "identity-bound `confirm`", "cap-rearming keep signal", "Rebase and regate",
        "daemon-soak passed-invoice reader",
        "reconstruct holds on restart", "never hold the bootstrap self-build"))
    assert set(CONTEXT["supervised-merge-hold"]).isdisjoint(ON_DEMAND)
    assert set(ON_DEMAND) | {"tests/test_supervised_merge_hold.py"} == set(FENCES["supervised-merge-hold"])


def test_continuation_pins_remaining_contracts_and_terminal_custody():
    scope = _scope("phase6-continue-06")
    assert _admissions("phase6-continue-06") == SUFFIX[1:]
    assert "section 20 alone" in scope and "never render section" in scope and "19" in scope
    assert "starts medium/medium unless" in scope and "KNOWN-DEEP or KNOWN-HARD high/high" in scope
    for stem, phrases in REMAINING.items():
        assert all(phrase in scope for phrase in phrases), stem
    [exit_line] = [line for line in scope.splitlines()
                   if line.startswith("`exit-receipt-machinery` depends on ")]
    exit_fence = exit_line.split("owns/fences", 1)[1].split(". It", 1)[0]
    assert _paths(exit_fence) == (
        "squatch/artifacts.py", "squatch/stages.py", "eval/host_loop.py",
        "tests/test_host_loop.py", "tests/test_gates.py", "tests/test_stages.py")
    for stem, depends, context in (
        ("phase6-continue-07", ("go-grade-machinery", "go-grade-run"), "tests/test_seeded_phase6_05.py"),
        ("phase6-continue-08", ("exit-receipt-machinery",), "tests/test_seeded_phase6_06.py"),
    ):
        [line] = [line for line in scope.splitlines() if line.startswith(f"`{stem}` depends on ")]
        assert _paths(line) == (stem, *depends, "tickets", f"tests/test_seeded_phase6_{int(stem[-2:]):02d}.py", context)
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
