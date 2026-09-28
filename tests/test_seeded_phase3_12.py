"""Heartbeat seed and the shrinking Phase 3 continuation."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket


REPO = Path(__file__).resolve().parent.parent
BATCH = {
    "heartbeat": ("phase3-continue-12",),
    "phase3-continue-13": ("heartbeat",),
}
OWNERSHIP = {
    "heartbeat": {
        "owns": ["squatch/heartbeat.py", "tests/test_heartbeat.py"],
        "hooks": ["squatch/daemon.py"],
    },
    "phase3-continue-13": {
        "owns": ["tickets", "tests/test_seeded_phase3_13.py"], "hooks": [],
    },
}
CONTEXT = {
    "heartbeat": (
        "tests/test_seeded_phase3_11.py", "squatch/daemon.py",
        "tests/test_daemon_tasks.py", "tests/test_control_cli.py",
        "tests/test_daemon_composition.py",
    ),
    "phase3-continue-13": (
        "tests/test_seeded_phase3_11.py", "squatch/daemon.py",
        "squatch/__main__.py", "tests/test_control_cli.py",
        "tests/test_daemon_composition.py",
    ),
}
EXISTING_AT_AUTHORING = {
    "tests/test_seeded_phase3_11.py": 9238,
    "squatch/daemon.py": 13795,
    "squatch/__main__.py": 17320,
    "tests/test_daemon_tasks.py": 6757,
    "tests/test_control_cli.py": 9688,
    "tests/test_daemon_composition.py": 21280,
}
# Measured from section 20 through its final newline when this batch was authored.
SECTION_20_CHARS_AT_AUTHORING = 16402
NEW_PATH_OWNERS = {
    "squatch/heartbeat.py": "heartbeat",
    "tests/test_heartbeat.py": "heartbeat",
    "tests/test_seeded_phase3_13.py": "phase3-continue-13",
    "squatch/restart.py": "restart-timers",
    "squatch/timers.py": "restart-timers",
    "tests/test_restart_timers.py": "restart-timers",
    "tests/test_seeded_phase3_14.py": "phase3-continue-14",
}
FULL = (
    ("heartbeat",), ("restart-timers",), ("flake-detection", "flake-release"),
    ("journal-roll", "storm-ledger"),
    ("storm-producer-wiring", "storm-notification-activation"),
    ("storm-dispatch-hold",), ("checkpoint-push",), ("daemon-soak",),
    ("soak-run",), ("phase3-exit",),
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


def test_exact_seeds_edges_tiers_budgets_cap_fences_and_new_path_owners():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert tuple(BATCH) == ("heartbeat", "phase3-continue-13")
    assert len(BATCH) <= config.seeding.max_seeds_per_admission == 3
    [contract] = [block["ownership"] for block in _yaml("phase3-continue-12")
                  if isinstance(block, dict) and "ownership" in block]
    assert contract == OWNERSHIP
    for stem, depends in BATCH.items():
        ticket = _ticket(stem)
        assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
        assert ticket.depends == depends and ticket.plan_sections == ("20",)
        assert (ticket.agent_tier, ticket.agent_effort) == ("medium", "medium")
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
        assert ticket.stuck_minutes <= config.drain.max_ticket_minutes
        assert ticket.scope_fence == tuple(OWNERSHIP[stem]["owns"] + OWNERSHIP[stem]["hooks"])
    assert NEW_PATH_OWNERS == {
        "squatch/heartbeat.py": "heartbeat", "tests/test_heartbeat.py": "heartbeat",
        "tests/test_seeded_phase3_13.py": "phase3-continue-13",
        "squatch/restart.py": "restart-timers", "squatch/timers.py": "restart-timers",
        "tests/test_restart_timers.py": "restart-timers",
        "tests/test_seeded_phase3_14.py": "phase3-continue-14",
    }


def test_context_closure_uses_existing_files_and_excludes_sibling_new_paths():
    for stem in BATCH:
        ticket = _ticket(stem)
        assert ticket.context == CONTEXT[stem]
        assert set(ticket.context) <= set(EXISTING_AT_AUTHORING)
        assert all((REPO / path).is_file() for path in ticket.context)
        assert set(ticket.context).isdisjoint(NEW_PATH_OWNERS)
        assert set(ticket.context).isdisjoint({"squatch/specs.py", "specs/implement.md"})
        for path in ticket.scope_fence:
            if path == "tickets":
                continue
            if path in NEW_PATH_OWNERS:
                assert NEW_PATH_OWNERS[path] == stem
            else:
                assert path in ticket.context, (stem, path)

    heartbeat = _ticket("heartbeat")
    predecessor = {"tests/test_daemon_tasks.py", "tests/test_control_cli.py",
                   "tests/test_daemon_composition.py"}
    assert predecessor <= set(heartbeat.context)
    assert predecessor.isdisjoint(heartbeat.scope_fence)


def test_heartbeat_ticket_repairs_the_testable_boundary_and_composition_proof():
    scope = _section("heartbeat", "Scope in")
    criteria = _section("heartbeat", "Acceptance criteria")
    assert "state directory" in scope and "state_dir / \"heartbeat\"" in criteria
    assert "filesystem seam" in scope and "clock seam" in scope
    assert "watcher, merge, and box" in scope
    assert "none is done or failed" in scope
    assert "starts no task or loop" in scope and "no `serve` CLI verb" in scope
    assert "composition hook" in criteria and "tests/test_heartbeat.py" in criteria
    assert "unfenced migration" not in criteria


def test_successor_uses_registry_roots_without_ungranted_inspection_exceptions():
    successor = _ticket("phase3-continue-13")
    assert "squatch/__main__.py" in successor.context
    assert "squatch/drain.py" not in successor.context
    scope = _section("phase3-continue-13", "Scope in")
    rejected = _section("phase3-continue-13", "Definition of rejected")
    assert "existing Context, not on-demand exceptions" in scope
    assert "Do not add `squatch/drain.py`" in scope
    assert "pending a plan fix" in rejected and "squatch/drain.py" in rejected


def test_authoring_sizes_and_max_effort_headroom():
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


def test_successor_removes_only_heartbeat_and_starts_at_restart_timers():
    assert _admissions("phase3-continue-12") == FULL
    successor = _admissions("phase3-continue-13")
    assert successor == FULL[1:]
    assert successor[0] == ("restart-timers",)
    stems = [stem for row in successor for stem in row]
    assert len(stems) == len(set(stems))
    assert "heartbeat" not in stems
