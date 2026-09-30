"""Row 6 GO-grade admission and terminal evidence custody."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket


REPO = Path(__file__).resolve().parent.parent
ROW = ("go-grade-machinery", "go-grade-run", "phase6-continue-07")
SUFFIX = (ROW, ("exit-receipt-machinery", "phase6-continue-08"), ("phase6-exit",))
FENCES = {
    "go-grade-machinery": (
        "eval/harness.py", "squatch/artifacts.py", "squatch/stages.py",
        "tests/test_eval_harness.py", "tests/test_stages.py", "tests/test_go_grade.py"),
    "go-grade-run": ("tickets/go-grade-run/review-baseline-report.json",),
    "phase6-continue-07": ("tickets", "tests/test_seeded_phase6_07.py"),
}
CONTEXT = {
    "go-grade-machinery": (),
    "go-grade-run": (),
    "phase6-continue-07": ("tests/test_seeded_phase6_05.py",),
}
REMAINING_FENCES = {
    "exit-receipt-machinery": (
        "squatch/artifacts.py", "squatch/stages.py", "eval/host_loop.py",
        "tests/test_host_loop.py", "tests/test_gates.py", "tests/test_stages.py"),
    "phase6-exit": (
        "tickets/phase6-exit/host-loop-report.json",
        "tickets/phase6-exit/exit-receipt.json", "tests/test_phase6_exit.py"),
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


def test_row_six_identity_edges_tier_fence_and_partition():
    assert _admissions("phase6-continue-06") == SUFFIX
    assert len(ROW) == load(REPO / "config.yaml", cwd=REPO).seeding.max_seeds_per_admission == 3
    edges = (("supervised-merge-hold", "fixture-host-scaffold"),
             ("go-grade-machinery",), ("go-grade-machinery", "go-grade-run"))
    for stem, depends in zip(ROW, edges, strict=True):
        ticket = _ticket(stem)
        assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
        assert ticket.depends == depends and ticket.scope_fence == FENCES[stem]
        assert ticket.context == CONTEXT[stem] and ticket.plan_sections == ("20",)
        assert (ticket.agent_tier, ticket.agent_effort) == ("medium", "medium")
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
        assert all((REPO / path).is_file() for path in ticket.context)
    scope = _scope("go-grade-machinery")
    on_demand = scope.split("Measured on-demand worktree reads:", 1)[1].split(". Read", 1)[0]
    assert _paths(on_demand) == FENCES["go-grade-machinery"][:-1]
    assert all((REPO / path).is_file() for path in _paths(on_demand))
    assert not set(CONTEXT["go-grade-machinery"]) & set(_paths(on_demand))
    for phrase in (
        "at least 50 planted defects", "USD 5.00 cap", "harness-local Author prompt is inline",
        "planted at runtime", "never uses production `specs/author.md`",
        "closed `review-baseline-report.json`", "planted-defect count", "spend",
        "authored tickets", "dependency graph", "verdict-signal identity",
        "`KNOWN_ARTIFACTS`", "`completed_output_lift`", "operator-only `--record-go`",
        "NO-GO", "run_seq keying is unchanged", "No non-operator path can write verdict GO",
        "test_run_scores_every_fixture_and_journals_the_no_go_signal",
        "test_rerun_after_a_recorded_verdict_takes_a_fresh_sequence_and_calls_again",
    ):
        assert phrase in scope
    machinery = _path("go-grade-machinery").read_text()
    acceptance = machinery.split("## Acceptance criteria", 1)[1].split("## Verification", 1)[0]
    assert "`tests/test_go_grade.py` alone proves" in acceptance
    assert "GO/binds=true through unchanged `resolve_baseline`" in acceptance
    assert "tests/test_baseline.py" not in acceptance
    assert "uv run pytest tests/test_baseline.py -q" in machinery.split("## Verification", 1)[1]
    run = _scope("go-grade-run")
    run_partition = run.split("Embedded Context:", 1)[1]
    embedded, measured = run_partition.split("; measured on-demand:", 1)
    assert _paths(embedded) == ()
    assert _paths(measured.split(". Read", 1)[0]) == (
        "eval/harness.py", "squatch/artifacts.py")
    assert all(phrase in run for phrase in (
        "changes no code", "merged harness once", "uncommitted for ordinary-lane",
        "GO-or-NO-GO verdict signal identity", "NO-GO is valid",
        "Only the", "operator may turn an earned result into GO", "must not invoke"))


def test_continuation_pins_remaining_contracts_and_terminal_custody():
    scope = _scope("phase6-continue-07")
    assert _admissions("phase6-continue-07") == SUFFIX[1:]
    assert SUFFIX[-1] == ("phase6-exit",)
    assert "section 20 alone" in scope and "never render section 19" in scope
    assert "starts medium/medium unless KNOWN-DEEP or KNOWN-HARD high/high" in scope
    for stem, fence in REMAINING_FENCES.items():
        [line] = [line for line in scope.splitlines() if line.startswith(f"`{stem}` depends on ")]
        ownership = line.split("owns/fences", 1)[1].split(". It", 1)[0]
        assert _paths(ownership) == fence
    assert all(phrase in scope for phrase in (
        "`exit-receipt-machinery` depends on `go-grade-run`",
        "closed writers for `host-loop-report.json` and `exit-receipt.json`",
        "supervised `serve`", "`hosts/fixture/`", "machine-actor confirms through the control inbox",
        "(member, driven scenario, observable, producing run)",
        "at least three machine-ticket merges", "report-to-regression bug loop", "escape attribution",
        "never produces terminal artifacts", "`phase6-exit` depends on `exit-receipt-machinery`",
        "transitively depends on every Phase 6 payload", "KNOWN-HARD high/high",
        "authors no successor", "accepts GO or NO-GO", "proves three members",
        "writes receipt digest", "makes no engine-code edit", "live-host K>=10",
        "runs the registered host-loop producer", "reads the committed GO-grade report",
        "and its embedded verdict identity", "three closed host-loop members",
        "real-host bug-loop evidence are forbidden exit inputs"))
    partition = scope.split("`exit-receipt-machinery` partition:", 1)[1].split("\n\n", 1)[0]
    embedded, on_demand = partition.split("; measured on-demand:")
    assert _paths(embedded) == ("squatch/artifacts.py", "tests/test_gates.py")
    assert _paths(on_demand) == ("squatch/stages.py", "tests/test_stages.py", "hosts/fixture/")
    assert "`phase6-exit` partition: Embedded Context: none; measured on-demand: none." in scope
    [line] = [line for line in scope.splitlines() if line.startswith("`phase6-continue-08` depends on ")]
    assert _paths(line) == ("phase6-continue-08", "exit-receipt-machinery", "tickets",
                            "tests/test_seeded_phase6_08.py", "tests/test_seeded_phase6_06.py")
    assert "The terminal row contains `phase6-exit` alone, has no successor, and authors no" in scope
    assert "continuation tail." in scope
    assert "phase6-continue-09" not in scope
    assert not (REPO / TICKETS_DIR / "phase6-continue-09").exists()


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
        assert not re.search(r"^## 19\. ", rendered, re.M)
        assert "Phase 5/6 compact-render correction (DECIDED" in rendered
        assert "Phase 6 remaining-row contracts (DECIDED)" in rendered
        assert len(rendered) <= limit, (stem, len(rendered), limit)
