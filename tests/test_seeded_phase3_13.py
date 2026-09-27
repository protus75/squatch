"""Restart timer seeds and the shrinking Phase 3 continuation."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket


REPO = Path(__file__).resolve().parent.parent
BATCH = {"restart-timers": ("phase3-continue-13",),
         "phase3-continue-14": ("restart-timers",)}
OWNERSHIP = {
    "restart-timers": {"owns": ["squatch/restart.py", "squatch/timers.py",
                                  "tests/test_restart_timers.py"],
                       "hooks": ["squatch/daemon.py", "squatch/__main__.py"]},
    "phase3-continue-14": {"owns": ["tickets", "tests/test_seeded_phase3_14.py"],
                            "hooks": []},
}
CONTEXT = {
    "restart-timers": ("tests/test_seeded_phase3_11.py", "squatch/daemon.py", "squatch/__main__.py",
                       "squatch/reconcile.py", "tests/test_reconcile.py",
                       "squatch/heartbeat.py", "tests/test_heartbeat.py",
                       "tests/test_control_cli.py", "tests/test_daemon_composition.py"),
    "phase3-continue-14": ("tests/test_seeded_phase3_11.py", "squatch/daemon.py",
                            "squatch/__main__.py", "tests/test_control_cli.py",
                            "tests/test_daemon_composition.py"),
}
EXISTING_AT_AUTHORING = {
    "tests/test_seeded_phase3_11.py": 9238, "squatch/daemon.py": 14440,
    "squatch/__main__.py": 17320, "squatch/reconcile.py": 5538,
    "tests/test_reconcile.py": 10334, "squatch/heartbeat.py": 1158,
    "tests/test_heartbeat.py": 3889, "tests/test_control_cli.py": 9688,
    "tests/test_daemon_composition.py": 21280,
}
NEW_PATH_OWNERS = {
    "squatch/restart.py": "restart-timers", "squatch/timers.py": "restart-timers",
    "tests/test_restart_timers.py": "restart-timers",
    "squatch/flake.py": "flake-detection", "tests/test_flake.py": "flake-detection",
    "tests/test_seeded_phase3_14.py": "phase3-continue-14",
    "tests/test_seeded_phase3_15.py": "phase3-continue-15",
}
FULL = (("restart-timers",), ("flake-detection", "flake-release"),
        ("journal-roll", "storm-ledger"),
        ("storm-producer-wiring", "storm-notification-activation"),
        ("storm-dispatch-hold",), ("checkpoint-push",), ("daemon-soak",),
        ("soak-run",), ("phase3-exit",))


def _path(stem):
    return REPO / TICKETS_DIR / stem / TICKET_FILE


def _ticket(stem):
    return lint_ticket(_path(stem).read_text(), stem=stem, repo=REPO,
                       plan=(REPO / PLAN_FILE).read_text(),
                       resolve_stem=lambda candidate: _path(candidate).is_file())


def _section(stem, name):
    lines = _path(stem).read_text().splitlines()
    start = lines.index(f"## {name}") + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


def _yaml(stem):
    return [yaml.safe_load(block) for block in re.findall(
        r"```yaml\n(.*?)\n```", _section(stem, "Scope in"), re.S)]


def _admissions(stem):
    [rows] = [block for block in _yaml(stem) if isinstance(block, list)]
    return tuple(tuple(row) for row in rows)


def test_exact_seeds_edges_tiers_budgets_cap_fences_and_new_path_owners():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert tuple(BATCH) == ("restart-timers", "phase3-continue-14")
    assert len(BATCH) <= config.seeding.max_seeds_per_admission == 3
    [contract] = [block["ownership"] for block in _yaml("phase3-continue-13")
                  if isinstance(block, dict) and "ownership" in block]
    assert contract == OWNERSHIP
    for stem, depends in BATCH.items():
        ticket = _ticket(stem)
        tiers = ("high", "high") if stem == "restart-timers" else ("medium", "medium")
        assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
        assert ticket.depends == depends and ticket.plan_sections == ("20",)
        assert (ticket.agent_tier, ticket.agent_effort) == tiers
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
        assert ticket.stuck_minutes <= config.drain.max_ticket_minutes
        assert ticket.scope_fence == tuple(OWNERSHIP[stem]["owns"] + OWNERSHIP[stem]["hooks"])
    assert NEW_PATH_OWNERS == {
        "squatch/restart.py": "restart-timers", "squatch/timers.py": "restart-timers",
        "tests/test_restart_timers.py": "restart-timers", "squatch/flake.py": "flake-detection",
        "tests/test_flake.py": "flake-detection", "tests/test_seeded_phase3_14.py": "phase3-continue-14",
        "tests/test_seeded_phase3_15.py": "phase3-continue-15",
    }


def test_context_fences_predecessor_closure_and_no_inspection_exception():
    for stem in BATCH:
        ticket = _ticket(stem)
        assert ticket.context == CONTEXT[stem]
        assert set(ticket.context) <= set(EXISTING_AT_AUTHORING)
        assert set(ticket.context).isdisjoint(NEW_PATH_OWNERS)
        assert set(ticket.context).isdisjoint({"squatch/specs.py", "specs/implement.md"})
        for path in ticket.scope_fence:
            if path in NEW_PATH_OWNERS:
                assert NEW_PATH_OWNERS[path] == stem
            elif path == "tickets":
                continue
            else:
                assert path in ticket.context, (stem, path)
    restart = _ticket("restart-timers")
    assert {"tests/test_control_cli.py", "tests/test_daemon_composition.py"} <= set(restart.context)
    assert "squatch/drain.py" not in restart.context and "squatch/drain.py" not in restart.scope_fence
    assert "on-demand Context exception" in _section("restart-timers", "Definition of rejected")


def test_restart_contract_delegates_reaping_and_makes_timers_journaled():
    scope = _section("restart-timers", "Scope in")
    criteria = _section("restart-timers", "Acceptance criteria")
    for phrase in ("delegates", "second reap path", "Journal seam", "injected Clock",
                   "journal fold", "compose_daemon_*", "side-file", "heartbeat remains dormant"):
        assert phrase in scope
    for phrase in ("re-arm once", "fires an expired deadline once", "never re-arm"):
        assert phrase in criteria


def test_authoring_sizes_and_max_effort_headroom():
    spec = load_spec(REPO / "specs" / "implement.md")
    plan = (REPO / PLAN_FILE).read_text()
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


def test_successor_removes_only_restart_and_starts_at_flake_pair():
    assert _admissions("phase3-continue-13") == FULL
    successor = _admissions("phase3-continue-14")
    assert successor == FULL[1:]
    stems = [stem for row in successor for stem in row]
    assert successor[0] == ("flake-detection", "flake-release")
    assert len(stems) == len(set(stems)) and "restart-timers" not in stems
