"""Terminal Phase 5 admission and its fixed Phase 6 core contract."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket


REPO = Path(__file__).resolve().parent.parent
EXIT = "phase5-exit"
PHASE5_STEMS = {
    "retro-drain-invoker", "retro-box-activation", "scorecard-reporting",
    "status-projection", "baseline-binding-reader", "retro-doctor-cli",
}
FENCE = ("tickets", "tests/test_phase5_exit.py", "tests/test_seeded_phase6_core.py")
EXIT_CONTEXT = (
    "tests/test_retro_box.py", "tests/test_baseline.py", "tests/test_seeded_phase5_03.py",
)
EXISTING_AT_AUTHORING = {
    "tests/test_retro_box.py": 29874,
    "tests/test_baseline.py": 5086,
    "tests/test_seeded_phase5_03.py": 7980,
}
SECTION_20_CHARS_AT_AUTHORING = 55841


def _path(stem):
    return REPO / TICKETS_DIR / stem / TICKET_FILE


def _ticket(stem):
    return lint_ticket(_path(stem).read_text(), stem=stem, repo=REPO,
                       plan=(REPO / PLAN_FILE).read_text(),
                       resolve_stem=lambda candidate: _path(candidate).is_file())


def _section(stem, name):
    lines = _path(stem).read_text().splitlines()
    start = lines.index(f"## {name}") + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")),
               len(lines))
    return "\n".join(lines[start:end])


def _flat(stem, section):
    return " ".join(_section(stem, section).split())


def _admissions(stem):
    [rows] = [yaml.safe_load(block) for block in re.findall(
        r"```yaml\n(.*?)\n```", _section(stem, "Scope in"), re.S)
        if isinstance(yaml.safe_load(block), list)]
    return tuple(tuple(row) for row in rows)


def _context(paths):
    return "".join(
        f"### {path}\n{'x' * EXISTING_AT_AUTHORING[path]}\n" for path in paths
    )


def _authoring_plan():
    current = (REPO / PLAN_FILE).read_text()
    start = current.index("## 20.")
    end = current.index("\n## ", start + 1) + 1
    heading = current[start:current.index("\n", start) + 1]
    section = heading + "x" * (SECTION_20_CHARS_AT_AUTHORING - len(heading) - 1) + "\n"
    return current[:start] + section + current[end:]


def test_terminal_exit_identity_transitive_boundary_tier_budget_and_fence():
    config = load(REPO / "config.yaml", cwd=REPO)
    ticket = _ticket(EXIT)
    assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
    assert ticket.depends == ("phase5-continue-04",)
    assert ticket.plan_sections == ("20",)
    assert (ticket.agent_tier, ticket.agent_effort) == ("high", "high")
    assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
    assert ticket.stuck_minutes <= config.drain.max_ticket_minutes
    assert ticket.scope_fence == FENCE

    seen, pending = set(), [EXIT]
    while pending:
        stem = pending.pop()
        if stem in seen:
            continue
        seen.add(stem)
        pending.extend(_ticket(stem).depends)
    assert PHASE5_STEMS <= seen


def test_context_partition_and_synthetic_render_headroom():
    continuation = _ticket("phase5-continue-04")
    assert continuation.context == ("tests/test_seeded_phase5_02.py",)
    assert (REPO / continuation.context[0]).is_file()
    assert set(continuation.context).isdisjoint({
        "tests/test_seeded_phase5_03.py", "tests/test_seeded_phase5_04.py",
    })

    ticket = _ticket(EXIT)
    assert ticket.context == EXIT_CONTEXT
    assert set(ticket.context) <= set(EXISTING_AT_AUTHORING)
    assert all((REPO / path).is_file() for path in ticket.context)
    assert set(ticket.context).isdisjoint(set(FENCE) | {"tests/test_seeded_phase5_04.py"})

    spec = load_spec(REPO / "specs" / "implement.md")
    rendered = spec.render({
        "workspace": DataBlock("engine", f"stem: {EXIT}\nbranch: {EXIT}\n"
                               f"run record: tickets/{EXIT}/{RUN_RECORD}\n"),
        "ticket": DataBlock("host", _path(EXIT).read_text()),
        "context": DataBlock("host", _context(ticket.context)),
    }, plan=_authoring_plan(), plan_sections=("20",), effort="max")
    assert len(rendered) <= int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)


def test_exit_text_pins_committed_evidence_and_read_write_boundaries():
    scope = _flat(EXIT, "Scope in")
    for text in (
        "clean checkout", "committed evidence only",
        "latest committed `tickets/retro/[0-9]{6}.md`",
        "forced pre-phase-exit hook", "after the latest Phase 5 feature merge",
        "merged `retro-drain-invoker`", "manual `retro` report is not accepted",
        "`## Surface scorecard`", "numeric spend/tokens", "only existing check surfaces",
        "zero escape column", "committed `tests/test_retro_box.py`",
        "`tickets/retro-box-activation/checks.json`", "committed `tests/test_baseline.py`",
        "`tickets/baseline-binding-reader/checks.json`", "Phase 1 NO-GO shape is unbound",
        "GO followed by spec-major drift is REVOKED", "every named Phase 5 dependency merged",
        "no live journal", "write no report", "never edit engine code",
    ):
        assert text in scope


def test_phase6_core_contract_context_exclusions_rows_and_headroom():
    scope = _flat(EXIT, "Scope in")
    for text in (
        "exactly confirmed medium/medium `core-renderer`, `core-drift-classifier`, and `phase6-continue`",
        "all citing section 20 alone", "`core-renderer` depends on `phase5-exit`",
        "`core-drift-classifier` depends on `core-renderer`",
        "`phase6-continue` depends on both construction stems", "new `squatch/hostfiles.py`",
        "new `tests/test_hostfiles.py`", "`squatch/__main__.py`, `tests/test_cli.py`, and `tests/test_verbs.py`",
        "Classifier owns `squatch/hostfiles.py` and `tests/test_hostfiles.py`",
        "owns only `tickets` and new `tests/test_seeded_phase6_01.py`",
        "embeds merged `tests/test_seeded_phase5_04.py`", "same-admission `tests/test_seeded_phase6_core.py`",
        "sibling-new `squatch/hostfiles.py` and `tests/test_hostfiles.py` paths",
        "`core-drift-activation`, `migrate-config`, continuation",
        "`host-contract-doc`, `fixture-host-scaffold`, continuation",
        "`bug-gate-grammar`, `report-inbox-triage`, continuation", "`escape-column`, continuation",
        "KNOWN-DEEP `supervised-merge-hold`, continuation",
        "`go-grade-machinery`, `go-grade-run`, continuation",
        "`exit-receipt-machinery`, continuation", "ending `phase6-exit` alone with no successor",
        "RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM", "none cites or renders section 19",
    ):
        assert text in scope


def test_terminal_registry_has_one_row_and_no_successor():
    assert _admissions("phase5-continue-04") == ((EXIT,),)
    scope = _flat("phase5-continue-04", "Scope in")
    assert "has no successor" in scope
    assert "phase5-continue-05" not in scope
    assert not (REPO / TICKETS_DIR / "phase5-continue-05").exists()
