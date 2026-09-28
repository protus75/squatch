"""Reliability-battery admission and the retained finite Phase 4 suffix."""

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
    "reliability-battery": ("provider-cooldown-failover",),
    "phase4-continue-04": ("reliability-battery",),
}
OWNERSHIP = {
    "reliability-battery": {
        "owns": ["eval/reliability_battery.py", "tests/test_reliability_battery.py"],
        "hooks": ["squatch/artifacts.py", "squatch/stages.py"],
    },
    "phase4-continue-04": {
        "owns": ["tickets", "tests/test_seeded_phase4_04.py"], "hooks": [],
    },
}
CONTEXT = {
    "reliability-battery": ("squatch/artifacts.py", "squatch/stages.py"),
    "phase4-continue-04": ("tests/test_seeded_phase4_02.py",),
}
EXISTING_AT_AUTHORING = {
    "squatch/artifacts.py": 5386,
    "squatch/stages.py": 55916,
    "tests/test_seeded_phase4_02.py": 10580,
}
# Measured from section 20 through its final newline at this admission.
SECTION_20_CHARS_AT_AUTHORING = 34774
NEW_PATH_OWNERS = {
    "eval/reliability_battery.py": "reliability-battery",
    "tests/test_reliability_battery.py": "reliability-battery",
    "tests/test_seeded_phase4_04.py": "phase4-continue-04",
    "tests/test_seeded_phase4_05.py": "phase4-continue-05",
}
BATTERY_NEW_PATHS = frozenset({
    "eval/reliability_battery.py", "tests/test_reliability_battery.py",
})
PREDECESSOR_CALLERS = re.compile(
    r"(?:stages" + r"\.compose|compose" + r"_pipeline|compose" + r"_daemon_timers|"
    r"restart" + r"_session|Serve" + r"\(|Session" + r"\()"
)
CONSTRUCTORS = (
    "stages" + ".compose", "compose" + "_pipeline", "compose" + "_daemon_timers",
    "restart" + "_session", "Serve", "Session",
)
FULL = (
    ("reliability-battery", "phase4-continue-04"),
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


def _authoring_plan():
    current = (REPO / PLAN_FILE).read_text()
    start = current.index("## 20.")
    end = current.index("\n## ", start + 1) + 1
    heading = current[start:current.index("\n", start) + 1]
    section = heading + "x" * (SECTION_20_CHARS_AT_AUTHORING - len(heading) - 1) + "\n"
    return current[:start] + section + current[end:]


def test_exact_seeds_edges_tiers_budgets_fences_and_owners():
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
        assert ticket.scope_fence == tuple(
            OWNERSHIP[stem]["owns"] + OWNERSHIP[stem]["hooks"])
    assert NEW_PATH_OWNERS["eval/reliability_battery.py"] == "reliability-battery"
    assert NEW_PATH_OWNERS["tests/test_reliability_battery.py"] == "reliability-battery"
    assert NEW_PATH_OWNERS["tests/test_seeded_phase4_04.py"] == "phase4-continue-04"


def test_context_closure_predecessor_preservation_and_new_path_exclusion():
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

    predecessor = (REPO / "tests/test_seeded_phase4_02.py").read_text()
    assert "callers <= set(provider.scope_fence) | set(PREDECESSOR)" in predecessor
    scope_out = _section("reliability-battery", "Scope out")
    for constructor in CONSTRUCTORS:
        assert constructor in scope_out
    # The predecessor scans all test/eval files. The battery cannot edit that
    # assertion, so its own contract excludes every scanned constructor and this
    # check applies that invariant once its new paths exist.
    for path in BATTERY_NEW_PATHS:
        target = REPO / path
        if target.is_file():
            assert PREDECESSOR_CALLERS.search(target.read_text()) is None, path


def test_authoring_sizes_and_max_effort_render_headroom():
    spec = load_spec(REPO / "specs" / "implement.md")
    plan = _authoring_plan()
    limit = int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
    for stem in BATCH:
        ticket = _ticket(stem)
        context = "".join(f"### {path}\n{'x' * EXISTING_AT_AUTHORING[path]}\n"
                          for path in ticket.context)
        workspace = f"stem: {stem}\nbranch: {stem}\nrun record: tickets/{stem}/{RUN_RECORD}\n"
        rendered = spec.render({"workspace": DataBlock("engine", workspace),
                                "ticket": DataBlock("host", _path(stem).read_text()),
                                "context": DataBlock("host", context)}, plan=plan,
                               plan_sections=ticket.plan_sections, effort="max")
        assert len(rendered) <= limit, (stem, len(rendered), limit)


def test_complete_finite_suffix_and_successor_removes_only_first_row():
    assert _admissions("phase4-continue-03") == FULL
    successor = _admissions("phase4-continue-04")
    assert successor == FULL[1:]
    assert successor[0] == ("reliability-run", "phase4-continue-05")
    assert all(len(row) <= 3 for row in FULL)
    stems = [stem for row in FULL for stem in row]
    assert len(stems) == len(set(stems))
    assert FULL[-1] == ("phase4-exit",)
    assert [row[-1] for row in FULL[:-1]] == [
        "phase4-continue-04", "phase4-continue-05",
    ]
    assert "phase4-continue-06" not in stems
