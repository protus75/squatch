"""Row 2 admission and the complete suffix that its successor must retain."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket


REPO = Path(__file__).resolve().parent.parent
ROW = ("host-contract-doc", "fixture-host-scaffold", "phase6-continue-03")
SUFFIX = (
    ROW, ("bug-gate-grammar", "report-inbox-triage", "phase6-continue-04"),
    ("escape-column", "phase6-continue-05"),
    ("supervised-merge-hold", "phase6-continue-06"),
    ("go-grade-machinery", "go-grade-run", "phase6-continue-07"),
    ("exit-receipt-machinery", "phase6-continue-08"), ("phase6-exit",),
)
CONTRACTS = {
    "bug-gate-grammar": (("fixture-host-scaffold",), ("squatch/tickets.py", "squatch/gates.py", "squatch/stages.py", "tests/test_tickets.py", "tests/test_gates.py", "tests/test_bug_gate.py"), ("squatch/tickets.py", "squatch/gates.py", "tests/test_tickets.py", "tests/test_gates.py"), ("squatch/stages.py",), ("`kind: bug`", "mandatory `## Regression`", "branch-head-pass/merge-base-with-`carries`-overlay-fail hard gate", "missing test at base is never accepted as defect evidence")),
    "report-inbox-triage": (("bug-gate-grammar",), ("squatch/inbox.py", "squatch/box.py", "squatch/triage.py", "squatch/author.py", "squatch/daemon.py", "tests/test_box.py", "tests/test_triage.py", "tests/test_author.py", "tests/test_inbox.py"), ("squatch/box.py", "squatch/triage.py", "tests/test_box.py", "tests/test_triage.py"), ("squatch/author.py", "squatch/daemon.py", "tests/test_author.py"), ("version-1 report schema", "metadata-first 1 MiB replay-file and 64 KiB log-excerpt caps", "durable Box custody", "`## Regression` survive intake")),
    "escape-column": (("bug-gate-grammar", "report-inbox-triage"), ("squatch/scorecard.py", "squatch/git.py", "tests/test_scorecard.py", "tests/test_git.py"), ("squatch/scorecard.py", "tests/test_scorecard.py"), ("squatch/git.py", "tests/test_git.py"), ("squash-trailer read operation", "deterministic bug-to-merged-ticket-or-bounded-range attribution", "increments escapes only for surfaces", "unattributed or foreign history out")),
    "supervised-merge-hold": (("escape-column",), ("squatch/merge.py", "squatch/baseline.py", "squatch/control.py", "squatch/__main__.py", "squatch/stages.py", "squatch/drain.py", "squatch/runner.py", "tests/test_merge.py", "tests/test_baseline.py", "tests/test_control_cli.py", "tests/test_cli.py", "tests/test_drain.py", "tests/test_supervised_merge_hold.py"), (), ("squatch/merge.py", "squatch/baseline.py", "squatch/control.py", "squatch/__main__.py", "squatch/stages.py", "squatch/drain.py", "squatch/runner.py", "tests/test_merge.py", "tests/test_baseline.py", "tests/test_control_cli.py", "tests/test_cli.py", "tests/test_drain.py"), ("KNOWN-DEEP high/high", "durable HELD admission", "identity-bound `confirm`", "rebase/regates", "never holds the bootstrap self-build")),
    "go-grade-machinery": (("supervised-merge-hold", "fixture-host-scaffold"), ("eval/harness.py", "squatch/artifacts.py", "tests/test_eval_harness.py", "tests/test_go_grade.py"), ("eval/harness.py", "squatch/artifacts.py", "tests/test_eval_harness.py"), (), ("at least 50 planted defects", "USD 5.00 cap", "operator-only `--record-go`", "never uses production `specs/author.md`")),
    "go-grade-run": (("go-grade-machinery",), ("tickets/go-grade-run/review-baseline-report.json",), ("eval/harness.py", "squatch/artifacts.py"), (), ("changes no code", "GO-or-NO-GO verdict signal identity", "NO-GO is valid")),
    "exit-receipt-machinery": (("go-grade-run",), ("squatch/artifacts.py", "eval/host_loop.py", "tests/test_host_loop.py", "tests/test_gates.py"), ("squatch/artifacts.py", "tests/test_gates.py"), ("hosts/fixture/",), ("closed writers for `host-loop-report.json` and `exit-receipt.json`", "supervised `serve`", "at least three machine-ticket merges", "report-to-regression bug loop", "escape attribution", "never produces terminal artifacts")),
    "phase6-exit": (("exit-receipt-machinery",), ("tickets/phase6-exit/host-loop-report.json", "tickets/phase6-exit/exit-receipt.json", "tests/test_phase6_exit.py"), (), (), ("KNOWN-HARD high/high", "authors no successor", "accepts GO or NO-GO", "writes receipt digest", "forbidden exit inputs")),
}
CONTINUATIONS = {
    "phase6-continue-04": (("bug-gate-grammar", "report-inbox-triage"), "tests/test_seeded_phase6_02.py"),
    "phase6-continue-05": (("escape-column",), "tests/test_seeded_phase6_03.py"),
    "phase6-continue-06": (("supervised-merge-hold",), "tests/test_seeded_phase6_04.py"),
    "phase6-continue-07": (("go-grade-machinery", "go-grade-run"), "tests/test_seeded_phase6_05.py"),
    "phase6-continue-08": (("exit-receipt-machinery",), "tests/test_seeded_phase6_06.py"),
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
    [rows] = [yaml.safe_load(block) for block in re.findall(r"```yaml\n(.*?)\n```", _scope(stem), re.S) if isinstance(yaml.safe_load(block), list)]
    return tuple(tuple(row) for row in rows)


def _paths(value):
    return tuple(re.findall(r"`([^`]+)`", value))


def test_row_two_identities_edges_tiers_fences_and_contexts():
    assert _admissions("phase6-continue-02") == SUFFIX
    assert len(ROW) <= load(REPO / "config.yaml", cwd=REPO).seeding.max_seeds_per_admission == 3
    expected = (("migrate-config",), ("host-contract-doc", "core-drift-activation"), ROW[:2])
    fences = (("docs/host-contract.md", "tests/test_host_contract.py"), ("hosts/fixture", "tests/test_fixture_host.py"), ("tickets", "tests/test_seeded_phase6_03.py"))
    contexts = ((), (), ("tests/test_seeded_phase6_01.py",))
    for stem, depends, fence, context in zip(ROW, expected, fences, contexts, strict=True):
        ticket = _ticket(stem)
        assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
        assert ticket.depends == depends and ticket.scope_fence == fence and ticket.context == context
        assert ticket.plan_sections == ("20",) and (ticket.agent_tier, ticket.agent_effort) == ("medium", "medium")
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
    assert "foreign process-state adoption" in _scope("host-contract-doc")
    assert "zero model spend" in _scope("fixture-host-scaffold")


def test_successor_pins_complete_remaining_contracts_and_partitions():
    scope = _scope("phase6-continue-03")
    assert _admissions("phase6-continue-03") == SUFFIX[1:]
    assert "section 20 alone" in scope and "never render section 19" in scope
    assert "starts medium/medium unless KNOWN-DEEP or KNOWN-HARD high/high" in scope
    for stem, (depends, fence, embedded, measured, behavior) in CONTRACTS.items():
        start = scope.index(f"`{stem}` ")
        segment = scope[start:scope.index("\n\n", start)]
        assert _paths(segment.split("owns/fences", 1)[0])[1:] == depends
        assert _paths(segment.split("owns/fences", 1)[1].split(". It", 1)[0]) == fence
        partition = re.search(rf"`{re.escape(stem)}` partition: Embedded Context: (.*?); measured on-demand: ([^\n]*)", scope)
        assert partition and _paths(partition.group(1)) == embedded and _paths(partition.group(2)) == measured
        assert all(phrase in segment for phrase in behavior), stem


def test_all_continuation_edges_terminal_custody_and_no_successor():
    scope = _scope("phase6-continue-03")
    for stem, (depends, context) in CONTINUATIONS.items():
        [line] = [line for line in scope.splitlines() if line.startswith(f"`{stem}` depends on ")]
        assert _paths(line) == (stem, *depends, "tickets", f"tests/test_seeded_phase6_{int(stem[-2:]):02d}.py", context)
    assert CONTRACTS["phase6-exit"][1] == ("tickets/phase6-exit/host-loop-report.json", "tickets/phase6-exit/exit-receipt.json", "tests/test_phase6_exit.py")
    assert "The terminal row contains `phase6-exit` alone, has no successor, and authors no continuation tail." in scope
    assert "phase6-continue-09" not in scope and not (REPO / TICKETS_DIR / "phase6-continue-09").exists()


def test_every_emitted_ticket_renders_with_real_context_at_max_effort():
    spec = load_spec(REPO / "specs" / "implement.md")
    plan = (REPO / PLAN_FILE).read_text()
    limit = int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
    for stem in ROW:
        ticket = _ticket(stem)
        context = "".join(f"### {path}\n{(REPO / path).read_text()}\n" for path in ticket.context)
        rendered = spec.render({"workspace": DataBlock("engine", f"stem: {stem}\nbranch: {stem}\nrun record: tickets/{stem}/{RUN_RECORD}\n"), "ticket": DataBlock("host", _path(stem).read_text()), "context": DataBlock("host", context)}, plan=plan, plan_sections=ticket.plan_sections, effort="max")
        assert ticket.plan_sections == ("20",)
        assert len(rendered) <= limit, (stem, len(rendered), limit)
