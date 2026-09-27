"""Production-serve and daemon-soak-runner continuation contracts."""

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
    "serve-activation": ("phase3-continue-20", "daemon-soak"),
    "phase3-continue-21": ("serve-activation",),
}
OWNERSHIP = {
    "serve-activation": {
        "owns": [
            "squatch/serve.py", "squatch/daemon.py", "squatch/__main__.py",
            "tests/test_serve.py", "tests/test_daemon_composition.py",
            "tests/test_daemon_tasks.py", "tests/test_kill_worker_stop.py",
            "tests/test_kill_failure_suppression.py", "tests/test_heartbeat.py",
            "tests/test_storm.py",
        ],
        "hooks": [],
    },
    "phase3-continue-21": {
        "owns": ["tickets", "tests/test_seeded_phase3_21.py"], "hooks": [],
    },
}
CONTEXT = {
    "serve-activation": (
        "squatch/daemon.py", "squatch/__main__.py",
        "tests/test_daemon_composition.py", "tests/test_daemon_tasks.py",
        "tests/test_heartbeat.py", "tests/test_storm.py",
    ),
    "phase3-continue-21": (
        "tests/test_seeded_phase3_11.py", "tests/test_daemon_composition.py",
    ),
}
ON_DEMAND = {
    "serve-activation": (
        "tests/test_kill_worker_stop.py", "tests/test_kill_failure_suppression.py",
    ),
}
EXISTING_AT_AUTHORING = {
    "squatch/daemon.py": 20131,
    "squatch/__main__.py": 18359,
    "tests/test_daemon_composition.py": 21280,
    "tests/test_daemon_tasks.py": 6757,
    "tests/test_heartbeat.py": 3889,
    "tests/test_storm.py": 5771,
    "tests/test_seeded_phase3_11.py": 9238,
}
NEW_PATH_OWNERS = {
    "squatch/serve.py": "serve-activation",
    "tests/test_serve.py": "serve-activation",
    "tests/test_seeded_phase3_21.py": "phase3-continue-21",
    "tests/test_daemon_soak_runner.py": "daemon-soak-runner",
    "tests/test_seeded_phase3_22.py": "phase3-continue-22",
    "tests/test_phase3_exit.py": "phase3-exit",
    "tests/test_seeded_phase4_core.py": "phase3-exit",
}
FULL = (
    ("serve-activation",), ("daemon-soak-runner",),
    ("soak-run",), ("phase3-exit",),
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


def _admissions(stem):
    [rows] = [block for block in _yaml(stem) if isinstance(block, list)]
    return tuple(tuple(row) for row in rows)


def test_exact_seeds_edges_tiers_budgets_cap_and_fences():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert tuple(BATCH) == ("serve-activation", "phase3-continue-21")
    assert len(BATCH) <= config.seeding.max_seeds_per_admission == 3
    [contract] = [block["ownership"] for block in _yaml("phase3-continue-20")
                  if isinstance(block, dict) and "ownership" in block]
    assert contract == OWNERSHIP
    for stem, depends in BATCH.items():
        ticket = _ticket(stem)
        tiers = ("high", "high") if stem == "serve-activation" else ("medium", "medium")
        assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
        assert ticket.depends == depends and ticket.plan_sections == ("20",)
        assert (ticket.agent_tier, ticket.agent_effort) == tiers
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
        assert ticket.stuck_minutes <= config.drain.max_ticket_minutes
        assert ticket.scope_fence == tuple(OWNERSHIP[stem]["owns"] + OWNERSHIP[stem]["hooks"])
        assert ticket.context == CONTEXT[stem]


def test_context_partition_predecessor_closure_and_new_path_owners():
    activation = _ticket("serve-activation")
    production_roots = {path for path in activation.context if path.startswith("squatch/")}
    predecessor_tests = {path for path in activation.context if path.startswith("tests/")}
    assert production_roots == {"squatch/daemon.py", "squatch/__main__.py"}
    assert predecessor_tests == {
        "tests/test_daemon_composition.py", "tests/test_daemon_tasks.py",
        "tests/test_heartbeat.py", "tests/test_storm.py",
    }
    assert set(ON_DEMAND["serve-activation"]).isdisjoint(activation.context)
    assert set(ON_DEMAND["serve-activation"]) <= set(activation.scope_fence)
    for stem in BATCH:
        ticket = _ticket(stem)
        assert set(ticket.context) <= set(EXISTING_AT_AUTHORING)
        assert set(ticket.context).isdisjoint(
            set(NEW_PATH_OWNERS) | {"squatch/specs.py", "specs/implement.md"})
        for path in ticket.scope_fence:
            if path != "tickets" and path not in NEW_PATH_OWNERS:
                assert path in ticket.context or path in ON_DEMAND.get(stem, ())
    assert NEW_PATH_OWNERS == {
        "squatch/serve.py": "serve-activation",
        "tests/test_serve.py": "serve-activation",
        "tests/test_seeded_phase3_21.py": "phase3-continue-21",
        "tests/test_daemon_soak_runner.py": "daemon-soak-runner",
        "tests/test_seeded_phase3_22.py": "phase3-continue-22",
        "tests/test_phase3_exit.py": "phase3-exit",
        "tests/test_seeded_phase4_core.py": "phase3-exit",
    }
    scope = _section("serve-activation", "Scope in")
    assert "replace the `serve`-absence assertions" in scope
    assert "production-root closure" in scope
    assert "only invalidated predecessor dormancy assertions" in scope


def test_authoring_sizes_and_max_effort_headroom():
    spec = load_spec(REPO / "specs" / "implement.md")
    plan = (REPO / PLAN_FILE).read_text()
    limit = int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
    for stem in BATCH:
        ticket = _ticket(stem)
        context = "".join(f"### {path}\n{'x' * EXISTING_AT_AUTHORING[path]}\n"
                          for path in ticket.context)
        workspace = f"stem: {stem}\nbranch: {stem}\nrun record: tickets/{stem}/{RUN_RECORD}\n"
        rendered = spec.render(
            {"workspace": DataBlock("engine", workspace),
             "ticket": DataBlock("host", _path(stem).read_text()),
             "context": DataBlock("host", context)},
            plan=plan, plan_sections=ticket.plan_sections, effort="max",
        )
        assert len(rendered) <= limit, (stem, len(rendered), limit)


def test_successor_pins_runner_and_terminal_suffix_after_removing_only_serve():
    continuation = _ticket("phase3-continue-21")
    assert _admissions("phase3-continue-20") == FULL
    assert _admissions("phase3-continue-21") == FULL[1:]
    [ownership] = [block["ownership"] for block in _yaml("phase3-continue-21")
                   if isinstance(block, dict) and "ownership" in block]
    assert ownership == {
        "daemon-soak-runner": {"owns": [
            "eval/daemon_soak.py", "tests/test_daemon_soak.py",
            "tests/test_daemon_soak_runner.py"], "hooks": []},
        "phase3-continue-22": {"owns": [
            "tickets", "tests/test_seeded_phase3_22.py"], "hooks": []},
    }
    [contexts] = [block["context"] for block in _yaml("phase3-continue-21")
                  if isinstance(block, dict) and "context" in block]
    assert {stem: tuple(paths) for stem, paths in contexts.items()} == {
        "daemon-soak-runner": (
            "tests/test_serve.py", "eval/daemon_soak.py", "tests/test_daemon_soak.py",
            "tests/test_audit.py"),
        "phase3-continue-22": ("tests/test_seeded_phase3_11.py", "tests/test_serve.py"),
    }
    scope = _section("phase3-continue-21", "Scope in")
    for phrase in (
        "`daemon-soak-runner` depends on `serve-activation`, is KNOWN-DEEP high/high",
        "`phase3-continue-22` depends on `daemon-soak-runner`, is medium/medium",
        "medium/medium no-code `soak-run`",
        "`soak-run` depends on `daemon-soak-runner` and produces only "
        "`tickets/soak-run/daemon-soak-report.json`",
        "`phase3-continue-23` authors KNOWN-HARD high/high `phase3-exit` alone and no successor",
        "the exit depends on `soak-run`, owns `tickets`, `tests/test_phase3_exit.py`, "
        "and `tests/test_seeded_phase4_core.py`",
        "`tests/test_restart_timers.py` and `tests/test_mergequeue.py` are on-demand "
        "fault-reference exceptions",
        "at least 24 injected hours",
        "member's local run evidence",
        "canonical writer",
        "REQ_RENDER_HEADROOM",
    ):
        assert phrase in scope
    criteria = _section("phase3-continue-21", "Acceptance criteria")
    for phrase in ("exact Context partition", "authoring-time Context sizes",
                   "predecessor-test closure", "max-effort render"):
        assert phrase in criteria
    assert continuation.context == CONTEXT["phase3-continue-21"]
