"""Terminal Phase 4 exit admission and the fixed Phase 5 core."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import DATA_MARKER, RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket


REPO = Path(__file__).resolve().parent.parent
STEM = "phase4-continue-05"
EXIT = "phase4-exit"
REPORT = "tickets/reliability-run/reliability-battery-report.json"
REPORT_MEMBERS = (
    "classified_quota_exhaustion",
    "all_candidates_cooling_recovery",
    "unclassified_failure_preservation",
)
CORE = ("retro-drain-invoker", "retro-box-activation", "phase5-continue")
FULL = (("reliability-run", STEM), (EXIT,))
CONTEXT = ("tests/test_seeded_phase4_03.py",)
EXIT_CONTEXT = (
    REPORT,
    "squatch/artifacts.py",
    "eval/reliability_battery.py",
    "tests/test_reliability_battery.py",
    "tests/test_seeded_phase4_02.py",
)
EXISTING_AT_AUTHORING = {
    REPORT: 1161,
    "squatch/artifacts.py": 7056,
    "eval/reliability_battery.py": 8811,
    "tests/test_reliability_battery.py": 3877,
    "tests/test_seeded_phase4_02.py": 10580,
    "tests/test_seeded_phase4_03.py": 7294,
}
# Measured from section 20 through its final newline at this admission.
SECTION_20_CHARS_AT_AUTHORING = 40233
NEW_PATH_OWNERS = {
    "tests/test_seeded_phase4_05.py": STEM,
    "tests/test_phase4_exit.py": EXIT,
    "tests/test_seeded_phase5_core.py": EXIT,
}


def _path(stem):
    return REPO / TICKETS_DIR / stem / TICKET_FILE


def _ticket(stem):
    return lint_ticket(
        _path(stem).read_text(), stem=stem, repo=REPO,
        plan=(REPO / PLAN_FILE).read_text(),
        resolve_stem=lambda candidate: _path(candidate).is_file(),
    )


def _section(stem, name):
    lines = _path(stem).read_text().splitlines()
    start = lines.index(f"## {name}") + 1
    end = next((index for index in range(start, len(lines))
                if lines[index].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


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


def test_terminal_identity_edge_tier_budget_fence_and_new_path_owners():
    config = load(REPO / "config.yaml", cwd=REPO)
    ticket = _ticket(EXIT)
    assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
    assert ticket.depends == ("reliability-run",)
    assert ticket.plan_sections == ("20",)
    assert (ticket.agent_tier, ticket.agent_effort) == ("high", "high")
    assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
    assert ticket.stuck_minutes <= config.drain.max_ticket_minutes
    assert ticket.scope_fence == (
        "tickets", "tests/test_phase4_exit.py", "tests/test_seeded_phase5_core.py",
    )

    tickets = {stem: _ticket(stem) for stem in (STEM, EXIT)}
    assert tickets[STEM].plan_sections == ("20",)
    assert tickets[STEM].expected_minutes <= tickets[STEM].stuck_minutes <= config.drain.max_ticket_minutes
    # Ownership must survive the exit creating its outputs in the live repo.
    for path, owner in NEW_PATH_OWNERS.items():
        other = EXIT if owner == STEM else STEM
        assert path in tickets[owner].scope_fence
        assert path not in tickets[other].scope_fence
        assert all(path not in ticket.context for ticket in tickets.values())

    scope = _section(STEM, "Scope in")
    assert f"committed\n`{REPORT}`" in scope
    assert "reads only the committed" in scope
    assert "never exit output" in scope


def test_context_closure_predecessor_preservation_and_sibling_exclusion():
    continuation = _ticket(STEM)
    assert continuation.context == CONTEXT
    exit_ticket = _ticket(EXIT)
    assert exit_ticket.context == EXIT_CONTEXT

    for ticket in (continuation, exit_ticket):
        assert set(ticket.context) <= set(EXISTING_AT_AUTHORING)
        assert set(ticket.context).isdisjoint(NEW_PATH_OWNERS)
        assert set(ticket.context).isdisjoint({"squatch/specs.py", "specs/implement.md"})
        for path in ticket.context:
            assert DATA_MARKER not in (REPO / path).read_text()
        for path in ticket.scope_fence:
            if path in NEW_PATH_OWNERS:
                assert NEW_PATH_OWNERS[path] == (STEM if ticket is continuation else EXIT)
            elif path != "tickets":
                assert path in ticket.context

    predecessor = (REPO / "tests/test_seeded_phase4_04.py").read_text()
    assert "successor == FULL[1:]" in predecessor
    assert "FULL[-1] == (\"phase4-exit\",)" in predecessor
    assert "Sibling-new paths are never Context." in _section(STEM, "Scope in")


def test_authoring_sizes_and_max_effort_render_headroom():
    spec = load_spec(REPO / "specs" / "implement.md")
    plan = _authoring_plan()
    limit = int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
    for stem in (STEM, EXIT):
        ticket = _ticket(stem)
        rendered = spec.render({
            "workspace": DataBlock(
                "engine", f"stem: {stem}\nbranch: {stem}\n"
                f"run record: tickets/{stem}/{RUN_RECORD}\n",
            ),
            "ticket": DataBlock("host", _path(stem).read_text()),
            "context": DataBlock("host", _context(ticket.context)),
        }, plan=plan, plan_sections=("20",), effort="max")
        assert len(rendered) <= limit, (stem, len(rendered), limit)


def test_terminal_suffix_cap_and_exact_phase5_core_report_contract():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert _admissions("phase4-continue-04") == FULL
    assert _admissions(STEM) == FULL[1:]
    assert all(len(row) <= config.seeding.max_seeds_per_admission == 3 for row in FULL)
    assert _admissions(STEM) == ((EXIT,),)
    assert all(len(row) <= config.seeding.max_seeds_per_admission
               for row in _admissions(STEM) + _admissions(EXIT))
    assert "phase4-continue-06" not in [stem for row in FULL for stem in row]

    scope = _section(EXIT, "Scope in")
    member_sentence = re.search(
        r"Its exact, complete member order is\n((?:`[a-z_]+`(?:, and\n|, |; )?)+)",
        scope,
    )
    assert member_sentence is not None
    assert tuple(re.findall(r"`([a-z_]+)`", member_sentence.group(1))) == REPORT_MEMBERS
    for obsolete in ("reliability-report.json", "spiral-notification", "hard-timeout"):
        assert obsolete not in scope
        assert all(obsolete not in path for path in _ticket(EXIT).context)
    assert f"Read only the committed `{REPORT}`" in scope
    assert "Author exactly confirmed `retro-drain-invoker`, `retro-box-activation`, and\n" \
           "`phase5-continue`" in scope
    assert _admissions(EXIT) == (CORE,)
    assert "scorecard-reporting" in scope
    assert "phase5-exit`, with no successor" in scope
    criteria = _section(EXIT, "Acceptance criteria")
    assert "`tests/test_phase4_exit.py` proves the committed report parses as `ReliabilityBatteryReport`" in criteria
    assert "closed three-member order, and every member is green before Phase 5 core authoring" in criteria
    assert "`tests/test_seeded_phase5_core.py` pins the exact three core identities, edges, tiers, budgets, fences, Context partitions" in criteria
    assert "fixed finite Phase 5 suffix" in criteria
    assert "uv run pytest tests/test_phase4_exit.py tests/test_seeded_phase5_core.py -q" in _section(EXIT, "Verification")
