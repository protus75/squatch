"""Daemon-soak-runner and terminal-continuation seed contracts."""

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
    "daemon-soak-runner": ("worker-recovery-disposition",),
    "phase3-continue-22": ("daemon-soak-runner",),
}
CORRECTION = "worker-recovery-disposition"
CORRECTION_DEPENDS = ("serve-merge-admission",)
CORRECTION_OWNERSHIP = {
    "owns": ["squatch/reconcile.py", "tests/test_reconcile.py"], "hooks": [],
}
CORRECTION_CONTEXT = ("squatch/reconcile.py", "tests/test_reconcile.py")
OWNERSHIP = {
    "daemon-soak-runner": {
        "owns": ["eval/daemon_soak.py", "tests/test_daemon_soak.py",
                 "tests/test_daemon_soak_runner.py"],
        "hooks": [],
    },
    "phase3-continue-22": {
        "owns": ["tickets", "tests/test_seeded_phase3_22.py"], "hooks": [],
    },
}
CONTEXT = {
    "daemon-soak-runner": (
        "tests/test_serve.py", "tests/test_merge.py", "eval/daemon_soak.py",
        "tests/test_daemon_soak.py", "tests/test_audit.py",
    ),
    "phase3-continue-22": ("tests/test_seeded_phase3_11.py", "tests/test_serve.py"),
}
ON_DEMAND = {
    "daemon-soak-runner": ("tests/test_restart_timers.py", "tests/test_mergequeue.py"),
}
EXISTING_AT_AUTHORING = {
    "tests/test_serve.py": 6235,
    "tests/test_merge.py": 22138,
    "eval/daemon_soak.py": 1142,
    "tests/test_daemon_soak.py": 3626,
    "tests/test_audit.py": 5267,
    "tests/test_seeded_phase3_11.py": 9238,
    "squatch/reconcile.py": 5538,
    "tests/test_reconcile.py": 10334,
}
PLAN_SECTION_AT_AUTHORING = 31984
NEW_PATH_OWNERS = {
    "tests/test_daemon_soak_runner.py": "daemon-soak-runner",
    "tests/test_seeded_phase3_22.py": "phase3-continue-22",
    "tickets/soak-run/daemon-soak-report.json": "soak-run",
    "tests/test_seeded_phase3_23.py": "phase3-continue-23",
    "tests/test_phase3_exit.py": "phase3-exit",
    "tests/test_seeded_phase4_core.py": "phase3-exit",
}
FULL = (("daemon-soak-runner",), ("soak-run",), ("phase3-exit",))


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
    assert tuple(BATCH) == ("daemon-soak-runner", "phase3-continue-22")
    assert len(BATCH) <= config.seeding.max_seeds_per_admission == 3
    [contract] = [block["ownership"] for block in _yaml("phase3-continue-21")
                  if isinstance(block, dict) and "ownership" in block]
    assert contract == OWNERSHIP
    for stem, depends in BATCH.items():
        ticket = _ticket(stem)
        tiers = ("high", "high") if stem == "daemon-soak-runner" else ("medium", "medium")
        assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
        assert ticket.depends == depends and ticket.plan_sections == ("20",)
        assert (ticket.agent_tier, ticket.agent_effort) == tiers
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
        assert ticket.stuck_minutes <= config.drain.max_ticket_minutes
        assert ticket.scope_fence == tuple(OWNERSHIP[stem]["owns"] + OWNERSHIP[stem]["hooks"])
        assert ticket.context == CONTEXT[stem]

    correction = _ticket(CORRECTION)
    assert (correction.source, correction.state, correction.priority) == (
        "seed", "confirmed", "P1")
    assert correction.depends == CORRECTION_DEPENDS
    assert correction.plan_sections == ("20",)
    assert (correction.agent_tier, correction.agent_effort) == ("high", "high")
    assert (correction.expected_minutes, correction.stuck_minutes) == (75, 150)
    assert correction.scope_fence == tuple(CORRECTION_OWNERSHIP["owns"])
    assert correction.context == CORRECTION_CONTEXT


def test_context_partition_fault_references_and_new_path_owners():
    runner = _ticket("daemon-soak-runner")
    observed_owners = {}
    assert set(ON_DEMAND["daemon-soak-runner"]).isdisjoint(runner.context)
    scope = _section("daemon-soak-runner", "Scope in")
    assert re.search(r"tests/test_restart_timers\.py` is the on-demand "
                     r"worker-reconcile fault\s+reference", scope)
    assert re.search(r"tests/test_mergequeue\.py` is the on-demand two-rung and\s+"
                     r"integration-red fault reference", scope)
    for stem in BATCH:
        ticket = _ticket(stem)
        assert set(ticket.context) <= set(EXISTING_AT_AUTHORING)
        assert set(ticket.context).isdisjoint(
            set(NEW_PATH_OWNERS) | {"squatch/specs.py", "specs/implement.md"})
        for path in ticket.scope_fence:
            if path in NEW_PATH_OWNERS:
                observed_owners[path] = stem
            elif path != "tickets":
                assert path in ticket.context

    [successor_ownership] = [
        block["ownership"] for block in _yaml("phase3-continue-22")
        if isinstance(block, dict) and "ownership" in block
    ]
    for stem, contract in successor_ownership.items():
        for path in contract["owns"]:
            if path != "tickets":
                observed_owners[path] = stem

    successor_scope = _section("phase3-continue-22", "Scope in")
    exit_ownership = re.search(
        r"`phase3-exit`.*?owns `([^`]+)`, `([^`]+)`, and\s+`([^`]+)`",
        successor_scope, re.S)
    assert exit_ownership
    for path in exit_ownership.groups():
        if path != "tickets":
            observed_owners[path] = "phase3-exit"
    assert observed_owners == NEW_PATH_OWNERS
    for phrase in ("at least 24 injected hours", "exactly `worker_killed_mid_run`, "
                   "`conflict_resolution_rungs`, and `semantic_conflict_integration_red`",
                   "member's local run evidence", "canonical writer"):
        assert phrase in scope
    for phrase in ("`recovery_alert`", "clean redispatched run's production terminal",
                   "never plant a second failure", "daily cadences fired"):
        assert phrase in scope

    correction_scope = _section(CORRECTION, "Scope in")
    for phrase in ("immediately after its `abandoned` state transition",
                   "before worktree removal", "kind `recovery_alert`",
                   "disposition `alert`", "outcome `abandoned`",
                   "does not duplicate the alert"):
        assert phrase in correction_scope


def test_authoring_sizes_predecessor_closure_and_max_effort_headroom():
    spec = load_spec(REPO / "specs" / "implement.md")
    plan = (REPO / PLAN_FILE).read_text()
    assert PLAN_SECTION_AT_AUTHORING == 31984
    start = plan.index("## 20.")
    body = plan.index("\n", start) + 1
    end = plan.index("\n## ", body) + 1
    plan = plan[:body] + "x" * (PLAN_SECTION_AT_AUTHORING - 1) + "\n" + plan[end:]
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

    correction = _ticket(CORRECTION)
    context = "".join(f"### {path}\n{'x' * EXISTING_AT_AUTHORING[path]}\n"
                      for path in correction.context)
    workspace = (f"stem: {CORRECTION}\nbranch: {CORRECTION}\n"
                 f"run record: tickets/{CORRECTION}/{RUN_RECORD}\n")
    rendered = spec.render(
        {"workspace": DataBlock("engine", workspace),
         "ticket": DataBlock("host", _path(CORRECTION).read_text()),
         "context": DataBlock("host", context)},
        plan=plan, plan_sections=correction.plan_sections, effort="max",
    )
    assert len(rendered) <= limit, (CORRECTION, len(rendered), limit)

    continuation = _ticket("phase3-continue-22")
    assert continuation.context == CONTEXT["phase3-continue-22"]
    assert "predecessor-test closure" in _section("phase3-continue-22", "Scope in")


def test_successor_removes_only_runner_and_pins_terminal_exit_custody():
    assert _admissions("phase3-continue-21") == FULL
    continuation = _ticket("phase3-continue-22")
    [ownership] = [block["ownership"] for block in _yaml("phase3-continue-22")
                   if isinstance(block, dict) and "ownership" in block]
    assert ownership == {
        "soak-run": {"owns": ["tickets/soak-run/daemon-soak-report.json"], "hooks": []},
        "phase3-continue-23": {
            "owns": ["tickets", "tests/test_seeded_phase3_23.py"], "hooks": []},
    }
    [contexts] = [block["context"] for block in _yaml("phase3-continue-22")
                  if isinstance(block, dict) and "context" in block]
    assert {stem: tuple(paths) for stem, paths in contexts.items()} == {
        "soak-run": ("eval/daemon_soak.py", "tests/test_daemon_soak_runner.py"),
        "phase3-continue-23": ("tests/test_seeded_phase3_11.py", "tests/test_serve.py"),
    }
    scope = _section("phase3-continue-22", "Scope in")
    assert re.search(r"`soak-run` depends on `daemon-soak-runner`,\s+"
                     r"is medium/medium", scope)
    assert re.search(r"`phase3-continue-23` depends on `soak-run`,\s+"
                     r"is medium/medium", scope)
    assert re.search(r"`phase3-exit`: it depends on `soak-run`,\s+"
                     r"is\s+KNOWN-HARD high/high", scope)
    for phrase in ("`daemon-soak-runner` as machinery and `soak-run` as producer",
                   "no successor", "REQ_RENDER_HEADROOM"):
        assert phrase in scope
    assert _admissions("phase3-continue-22") == (("soak-run",), ("phase3-exit",))
    assert _admissions("phase3-continue-22") == FULL[1:]
    assert continuation.depends == ("daemon-soak-runner",)
