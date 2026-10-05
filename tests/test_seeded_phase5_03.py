"""Third Phase 5 admission: operator verbs and the terminal continuation."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import DATA_MARKER, RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket


REPO = Path(__file__).resolve().parent.parent
DOCTOR = "retro-doctor-cli"
CONTINUE = "phase5-continue-04"
ROW = (DOCTOR, CONTINUE)
FULL = (ROW, ("phase5-exit",))
CONTEXT = {DOCTOR: ("squatch/retro.py", "tests/test_retro.py"),
           CONTINUE: ("tests/test_seeded_phase5_02.py",)}
FENCES = {
    DOCTOR: ("squatch/doctor.py", "tests/test_doctor.py", "squatch/retro.py",
             "squatch/__main__.py", "tests/test_retro.py", "tests/test_cli.py",
             "tests/test_verbs.py"),
    CONTINUE: ("tickets", "tests/test_seeded_phase5_04.py"),
}
EXISTING_AT_AUTHORING = {"squatch/retro.py": 17745, "tests/test_retro.py": 20072,
                         "tests/test_seeded_phase5_02.py": 11383}
ON_DEMAND = {"squatch/__main__.py": 24624, "tests/test_cli.py": 19367,
             "tests/test_verbs.py": 9901}
SIBLING_NEW = {"tests/test_seeded_phase5_03.py", "tests/test_seeded_phase5_04.py",
               "squatch/doctor.py", "tests/test_doctor.py"}
SECTION_20_CHARS_AT_AUTHORING = 55841


def _path(stem):
    return REPO / TICKETS_DIR / stem / TICKET_FILE


def _ticket(stem):
    return lint_ticket(_path(stem).read_text(), stem=stem, repo=REPO,
                       plan=(REPO / "tests/fixtures/squatch_plan_v1.md").read_text(),
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
    return "".join(f"### {path}\n{'x' * EXISTING_AT_AUTHORING[path]}\n" for path in paths)


def _authoring_plan():
    current = (REPO / "tests/fixtures/squatch_plan_v1.md").read_text()
    start = current.index("## 20.")
    end = current.index("\n## ", start + 1) + 1
    heading = current[start:current.index("\n", start) + 1]
    section = heading + "x" * (SECTION_20_CHARS_AT_AUTHORING - len(heading) - 1) + "\n"
    return current[:start] + section + current[end:]


def test_rows_edges_tiers_budgets_fences_and_cap():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert _admissions("phase5-continue-03") == FULL
    assert len(ROW) <= config.seeding.max_seeds_per_admission == 3
    for stem, depends in {DOCTOR: ("status-projection", "baseline-binding-reader"),
                          CONTINUE: (DOCTOR,)}.items():
        ticket = _ticket(stem)
        assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
        assert ticket.depends == depends and ticket.plan_sections == ("20",)
        assert (ticket.agent_tier, ticket.agent_effort) == ("medium", "medium")
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
        assert ticket.stuck_minutes <= config.drain.max_ticket_minutes
        assert ticket.scope_fence == FENCES[stem]


def test_context_partition_synthetic_sizes_and_render_headroom():
    assert EXISTING_AT_AUTHORING["tests/test_seeded_phase5_02.py"] == 11383
    for stem, paths in CONTEXT.items():
        ticket = _ticket(stem)
        assert ticket.context == paths and set(paths) <= set(EXISTING_AT_AUTHORING)
        assert set(paths).isdisjoint(SIBLING_NEW)
        assert all(DATA_MARKER not in (REPO / path).read_text() for path in paths)
    scope = _flat(DOCTOR, "Scope in")
    for path, size in ON_DEMAND.items():
        assert f"`{path}` ({size} bytes)" in scope
    spec = load_spec(REPO / "specs" / "implement.md")
    limit = int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
    for stem in ROW:
        rendered = spec.render({
            "workspace": DataBlock("engine", f"stem: {stem}\nbranch: {stem}\nrun record: tickets/{stem}/{RUN_RECORD}\n"),
            "ticket": DataBlock("host", _path(stem).read_text()),
            "context": DataBlock("host", _context(CONTEXT[stem])),
        }, plan=_authoring_plan(), plan_sections=("20",), effort="max")
        assert len(rendered) <= limit, (stem, len(rendered), limit)


def test_doctor_seed_feature_criteria_cover_both_verbs_only():
    criteria = _flat(DOCTOR, "Acceptance criteria")
    for text in ("five ordered injected-seam checks", "exact rendering", "0/2 exits",
                 "manual retro no-merge, successful committed-report, and selected failure",
                 "exit classes for both verbs", "manual `retro`", "provider-free `doctor`"):
        assert text in criteria
    assert "test_seeded_phase5_03.py" not in criteria
    assert "synthetic" not in criteria and "partition" not in criteria and "size" not in criteria
    for path in ("tests/test_doctor.py", "tests/test_retro.py", "tests/test_cli.py", "tests/test_verbs.py"):
        assert path in _section(DOCTOR, "Verification")


def test_terminal_continuation_pins_exit_disposition_and_phase6_registry():
    scope = _flat(CONTINUE, "Scope in")
    assert _admissions(CONTINUE) == (("phase5-exit",),)
    for text in (
        "KNOWN-HARD high/high", "depends transitively on every Phase 5 stem",
        "owns only `tickets`, new `tests/test_phase5_exit.py`, and new `tests/test_seeded_phase6_core.py`",
        "has no successor", "clean checkout and reads committed evidence only",
        "latest committed `tickets/retro/[0-9]{6}.md`", "forced pre-phase-exit hook",
        "`retro-drain-invoker`", "manual `retro` report is not accepted", "`## Surface scorecard`",
        "numeric spend/tokens", "zero escape column", "no live journal",
        "`tickets/retro-box-activation/checks.json`", "`tickets/baseline-binding-reader/checks.json`",
        "exactly confirmed medium/medium `core-renderer`, `core-drift-classifier`, and `phase6-continue`",
        "`core-renderer` depends on `phase5-exit`", "`core-drift-classifier` depends on `core-renderer`",
        "`phase6-continue` depends on both construction stems", "new `squatch/hostfiles.py`",
        "new `tests/test_hostfiles.py`", "new `tests/test_seeded_phase6_01.py`",
        "embeds merged `tests/test_seeded_phase5_04.py`", "`core-drift-activation`, `migrate-config`, continuation",
        "`host-contract-doc`, `fixture-host-scaffold`, continuation",
        "`bug-gate-grammar`, `report-inbox-triage`, continuation", "`escape-column`, continuation",
        "KNOWN-DEEP `supervised-merge-hold`, continuation",
        "`go-grade-machinery`, `go-grade-run`, continuation",
        "`exit-receipt-machinery`, continuation", "ending `phase6-exit` alone with no successor",
    ):
        assert text in scope
    assert "phase5-continue-05" not in scope


def test_exit_and_phase6_contracts_use_section20_only_and_compact_headroom():
    scope = _flat(CONTINUE, "Scope in")
    assert "cites section 20 alone" in scope
    assert "none cites or renders section 19" in scope
    assert "RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM" in scope
    section20 = (REPO / "tests/fixtures/squatch_plan_v1.md").read_text()
    section20 = section20[section20.index("## 20."):]
    for text in (
        "Phase 5/6 compact-render correction", "cite section 20 ALONE",
        "full section 19 is never rendered", "The remaining Phase 6 admissions are fixed here",
        "no historical section-19 snapshot or live section-19 render is accepted",
    ):
        assert text in section20
