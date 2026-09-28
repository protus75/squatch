"""Terminal Phase 3 exit seed contract."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket


REPO = Path(__file__).resolve().parent.parent
STEM = "phase3-exit"
OWNERSHIP = {
    STEM: {
        "owns": ["tickets", "tests/test_phase3_exit.py", "tests/test_seeded_phase4_core.py"],
        "hooks": [],
    },
}
CONTEXT = {
    STEM: (
        "tickets/soak-run/daemon-soak-report.json", "squatch/artifacts.py",
        "eval/daemon_soak.py", "tests/test_daemon_soak_runner.py",
        "tests/test_seeded_phase3_11.py",
    ),
}
EXISTING_AT_AUTHORING = {
    "tickets/soak-run/daemon-soak-report.json": 1629,
    "squatch/artifacts.py": 5386,
    "eval/daemon_soak.py": 25471,
    "tests/test_daemon_soak_runner.py": 12245,
    "tests/test_seeded_phase3_11.py": 9238,
}
# Section 20 including its heading when this terminal Phase 3 seed was authored.
SECTION_20_CHARS_AT_AUTHORING = 31857
NEW_PATH_OWNERS = {
    "tests/test_phase3_exit.py": STEM,
    "tests/test_seeded_phase4_core.py": STEM,
}
PHASE4_CORE = {
    "watchdog-event-stream": {
        "depends": ("phase3-exit",),
        "owns": ("squatch/watchdog.py", "squatch/providers.py", "tests/test_watchdog.py",
                 "tests/test_providers.py"),
    },
    "notify-transport": {
        "depends": ("phase3-exit",),
        "owns": ("squatch/notify.py", "squatch/config.py", "squatch/seams.py",
                 "tests/test_notify.py", "tests/test_config.py", "tests/test_seams.py"),
    },
    "phase4-continue": {
        "depends": ("watchdog-event-stream", "notify-transport"),
        "owns": ("tickets", "tests/test_seeded_phase4_01.py"),
    },
}
PHASE4_SUFFIX = (
    "watchdog-detector", "watchdog-activation", "provider-cooldown-failover",
    "reliability-battery", "reliability-run", "phase4-exit",
)


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
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")),
               len(lines))
    return "\n".join(lines[start:end])


def _yaml(stem):
    return [yaml.safe_load(block) for block in re.findall(
        r"```yaml\n(.*?)\n```", _section(stem, "Scope in"), re.S)]


def _phase4_registry():
    plan = (REPO / PLAN_FILE).read_text()
    start = plan.index("Phase 4 boundary registry (DECIDED):")
    return plan[start:plan.index("`phase3-continue-23` fences", start)]


def _authoring_plan():
    current = (REPO / PLAN_FILE).read_text()
    start = current.index("## 20.")
    end = current.index("\n## ", start + 1) + 1
    heading = current[start:current.index("\n", start) + 1]
    section = heading + "x" * (SECTION_20_CHARS_AT_AUTHORING - len(heading) - 1) + "\n"
    return current[:start] + section + current[end:]


def _in_order(text, stems):
    indices = [text.index(f"`{stem}`") for stem in stems]
    assert indices == sorted(indices)


def test_exit_identity_dependency_tier_budget_cap_and_owns_then_hooks_fence():
    config = load(REPO / "config.yaml", cwd=REPO)
    ticket = _ticket(STEM)
    assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
    assert ticket.depends == ("soak-run",)
    assert ticket.plan_sections == ("20",)
    assert (ticket.agent_tier, ticket.agent_effort) == ("high", "high")
    assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
    assert ticket.stuck_minutes <= config.drain.max_ticket_minutes
    assert config.seeding.max_seeds_per_admission == 3
    assert ticket.scope_fence == tuple(OWNERSHIP[STEM]["owns"] + OWNERSHIP[STEM]["hooks"])

    [contract] = [block["ownership"] for block in _yaml("phase3-continue-23")
                  if isinstance(block, dict) and "ownership" in block]
    assert contract == OWNERSHIP


def test_context_partition_sizes_predecessor_closure_and_new_owners():
    ticket = _ticket(STEM)
    assert ticket.context == CONTEXT[STEM]
    assert set(ticket.context) <= set(EXISTING_AT_AUTHORING)
    assert set(ticket.context).isdisjoint(
        set(NEW_PATH_OWNERS) | {"squatch/specs.py", "specs/implement.md"})
    for path in ticket.scope_fence:
        if path in NEW_PATH_OWNERS:
            assert NEW_PATH_OWNERS[path] == STEM
        elif path != "tickets":
            assert path in ticket.context

    [contexts] = [block["context"] for block in _yaml("phase3-continue-23")
                  if isinstance(block, dict) and "context" in block]
    assert {stem: tuple(paths) for stem, paths in contexts.items()} == CONTEXT
    scope = _section("phase3-continue-23", "Scope in")
    for phrase in ("authoring-time Context sizes", "predecessor-test closure", "sibling-new",
                   "squatch/specs.py"):
        assert phrase in scope
    exit_scope = _section(STEM, "Scope in")
    assert "`DaemonSoakReport` using its owner\n`squatch/artifacts.py`" in exit_scope


def test_report_custody_singleton_admission_and_no_successor():
    scope = _section("phase3-continue-23", "Scope in")
    assert re.search(r"`phase3-exit`, which depends on\s+`soak-run`", scope)
    assert "daemon-soak-runner` as machinery" in scope
    assert "soak-run` as producer" in scope
    assert "There is no successor after `phase3-exit`." in scope
    [admission] = [block for block in _yaml("phase3-continue-23") if isinstance(block, list)]
    assert tuple(tuple(row) for row in admission) == ((STEM,),)

    exit_scope = _section(STEM, "Scope in")
    for phrase in ("committed-artifact-only", "DaemonSoakReport", "injected_hours >=",
                   "daemon-soak-runner` is machinery", "soak-run` is producer"):
        assert phrase in exit_scope


def test_phase4_registry_core_edges_owners_and_ordered_suffix():
    registry = _phase4_registry()
    exit_scope = _section(STEM, "Scope in")
    assert tuple(PHASE4_CORE) == (
        "watchdog-event-stream", "notify-transport", "phase4-continue")
    _in_order(registry, PHASE4_CORE)
    _in_order(exit_scope, PHASE4_CORE)
    for stem, contract in PHASE4_CORE.items():
        for path in contract["owns"]:
            assert f"`{path}`" in registry
            assert f"`{path}`" in exit_scope
        for dependency in contract["depends"]:
            assert f"`{dependency}`" in registry
            assert f"`{dependency}`" in exit_scope
    assert "The first two depend on `phase3-exit`" in registry
    assert "`phase4-continue` depends on both" in registry
    assert "machinery seeds depend on `phase3-exit`" in exit_scope
    assert "`phase4-continue` depends on both machinery stems" in exit_scope
    _in_order(registry, PHASE4_SUFFIX)
    _in_order(exit_scope, PHASE4_SUFFIX)
    assert "`provider-cooldown-failover` (KNOWN-DEEP, alone)" in registry
    assert "`phase4-exit` (KNOWN-HARD high/high, alone and last)" in registry
    assert "`provider-cooldown-failover` alone" in exit_scope
    assert "`phase4-exit` alone and last" in exit_scope


def test_authoring_time_max_effort_render_headroom():
    spec = load_spec(REPO / "specs" / "implement.md")
    ticket = _ticket(STEM)
    context = "".join(f"### {path}\n{'x' * EXISTING_AT_AUTHORING[path]}\n"
                      for path in ticket.context)
    workspace = f"stem: {STEM}\nbranch: {STEM}\nrun record: tickets/{STEM}/{RUN_RECORD}\n"
    rendered = spec.render(
        {"workspace": DataBlock("engine", workspace),
         "ticket": DataBlock("host", _path(STEM).read_text()),
         "context": DataBlock("host", context)},
        plan=_authoring_plan(), plan_sections=ticket.plan_sections,
        effort="max",
    )
    assert len(rendered) <= int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
