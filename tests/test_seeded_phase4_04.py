"""Reliability-run admission and the terminal Phase 4 suffix."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import DATA_MARKER, RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket


REPO = Path(__file__).resolve().parent.parent
BATCH = {
    "reliability-run": ("reliability-battery",),
    "phase4-continue-05": ("reliability-run",),
}
OWNERSHIP = {
    "reliability-run": {
        "owns": ["tickets/reliability-run/reliability-battery-report.json"], "hooks": [],
    },
    "phase4-continue-05": {
        "owns": ["tickets", "tests/test_seeded_phase4_05.py"], "hooks": [],
    },
    "phase4-exit": {
        "owns": ["tickets", "tests/test_phase4_exit.py", "tests/test_seeded_phase5_core.py"],
        "hooks": [],
    },
}
CONTEXT = {
    "reliability-run": (
        "eval/reliability_battery.py", "squatch/artifacts.py",
        "tests/test_reliability_battery.py",
    ),
    "phase4-continue-05": ("tests/test_seeded_phase4_03.py",),
}
EXIT_CONTEXT = (
    "tickets/reliability-run/reliability-battery-report.json",
    "squatch/artifacts.py", "eval/reliability_battery.py",
    "tests/test_reliability_battery.py", "tests/test_seeded_phase4_02.py",
)
ON_DEMAND = {"squatch/stages.py"}
EXISTING_AT_AUTHORING = {
    "tickets/reliability-run/reliability-battery-report.json": 1161,
    "eval/reliability_battery.py": 8811,
    "squatch/artifacts.py": 7056,
    "squatch/stages.py": 56079,
    "tests/test_reliability_battery.py": 3877,
    "tests/test_seeded_phase4_02.py": 10580,
    "tests/test_seeded_phase4_03.py": 7294,
}
# Measured from section 20 through its final newline at this admission.
SECTION_20_CHARS_AT_AUTHORING = 59764
NEW_PATH_OWNERS = {
    "tickets/reliability-run/reliability-battery-report.json": "reliability-run",
    "tests/test_seeded_phase4_05.py": "phase4-continue-05",
    "tests/test_phase4_exit.py": "phase4-exit",
    "tests/test_seeded_phase5_core.py": "phase4-exit",
}
FULL = (
    ("reliability-run", "phase4-continue-05"),
    ("phase4-exit",),
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
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")),
               len(lines))
    return "\n".join(lines[start:end])


def _yaml(stem):
    return [yaml.safe_load(block) for block in re.findall(
        r"```yaml\n(.*?)\n```", _section(stem, "Scope in"), re.S)]


def _admissions(stem):
    [rows] = [block for block in _yaml(stem) if isinstance(block, list)]
    return tuple(tuple(row) for row in rows)


def _context(paths):
    return "".join(f"### {path}\n{'x' * EXISTING_AT_AUTHORING[path]}\n" for path in paths)


def _authoring_plan():
    current = (REPO / PLAN_FILE).read_text()
    start = current.index("## 20.")
    end = current.index("\n## ", start + 1) + 1
    heading = current[start:current.index("\n", start) + 1]
    section = heading + "x" * (SECTION_20_CHARS_AT_AUTHORING - len(heading) - 1) + "\n"
    return current[:start] + section + current[end:]


def test_exact_seeds_edges_tiers_budgets_fences_and_new_path_owners():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert tuple(BATCH) == FULL[0]
    assert len(BATCH) <= config.seeding.max_seeds_per_admission == 3
    for stem, depends in BATCH.items():
        ticket = _ticket(stem)
        assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
        assert ticket.depends == depends and ticket.plan_sections == ("20",)
        assert (ticket.agent_tier, ticket.agent_effort) == ("medium", "medium")
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
        assert ticket.stuck_minutes <= config.drain.max_ticket_minutes
        assert ticket.scope_fence == tuple(OWNERSHIP[stem]["owns"] + OWNERSHIP[stem]["hooks"])
    assert NEW_PATH_OWNERS == {
        "tickets/reliability-run/reliability-battery-report.json": "reliability-run",
        "tests/test_seeded_phase4_05.py": "phase4-continue-05",
        "tests/test_phase4_exit.py": "phase4-exit",
        "tests/test_seeded_phase5_core.py": "phase4-exit",
    }


def test_context_closure_predecessor_preservation_and_delimiter_exclusion():
    for stem in BATCH:
        ticket = _ticket(stem)
        assert ticket.context == CONTEXT[stem]
        assert set(ticket.context) <= set(EXISTING_AT_AUTHORING)
        assert set(ticket.context).isdisjoint(NEW_PATH_OWNERS)
        assert set(ticket.context).isdisjoint({"squatch/specs.py", "specs/implement.md"})
        for path in ticket.context:
            assert DATA_MARKER not in (REPO / path).read_text()
        for path in ticket.scope_fence:
            if path in NEW_PATH_OWNERS:
                assert NEW_PATH_OWNERS[path] == stem
            elif path != "tickets":
                assert path in ticket.context, (stem, path)
    scope = _section("reliability-run", "Scope in")
    assert "`squatch/stages.py` is a measured\non-demand headroom exception" in scope
    assert ON_DEMAND.isdisjoint(_ticket("reliability-run").context)
    assert all((REPO / path).is_file() for path in ON_DEMAND)
    predecessor = (REPO / "tests/test_seeded_phase4_03.py").read_text()
    assert "PREDECESSOR_CALLERS.search(target.read_text()) is None" in predecessor
    continuation_scope = _section("phase4-continue-05", "Scope in")
    for path in EXIT_CONTEXT:
        assert f"`{path}`" in continuation_scope
        assert DATA_MARKER not in (REPO / path).read_text()
    assert "committed\n`tickets/reliability-run/reliability-battery-report.json`" in continuation_scope
    assert "the report is existing Context owned by `reliability-run`, never exit output" in continuation_scope


def test_authoring_sizes_and_max_effort_render_headroom():
    spec = load_spec(REPO / "specs" / "implement.md")
    plan = _authoring_plan()
    limit = int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
    for stem in BATCH:
        ticket = _ticket(stem)
        rendered = spec.render({
            "workspace": DataBlock("engine", f"stem: {stem}\nbranch: {stem}\n"
                                   f"run record: tickets/{stem}/{RUN_RECORD}\n"),
            "ticket": DataBlock("host", _path(stem).read_text()),
            "context": DataBlock("host", _context(ticket.context)),
        }, plan=plan, plan_sections=ticket.plan_sections, effort="max")
        assert len(rendered) <= limit, (stem, len(rendered), limit)
    assert set(EXIT_CONTEXT) <= set(EXISTING_AT_AUTHORING)
    assert (set(EXIT_CONTEXT) - {
        "tickets/reliability-run/reliability-battery-report.json"
    }).isdisjoint(NEW_PATH_OWNERS)
    assert NEW_PATH_OWNERS["tickets/reliability-run/reliability-battery-report.json"] == "reliability-run"


def test_complete_finite_suffix_and_successor_removes_only_first_row():
    assert _admissions("phase4-continue-04") == FULL
    successor = _admissions("phase4-continue-05")
    assert successor == FULL[1:]
    assert successor[0] == ("phase4-exit",)
    assert all(len(row) <= 3 for row in FULL)
    stems = [stem for row in FULL for stem in row]
    assert len(stems) == len(set(stems))
    assert [row[-1] for row in FULL[:-1]] == ["phase4-continue-05"]
    assert FULL[-1] == ("phase4-exit",)
    assert "phase4-continue-06" not in stems
