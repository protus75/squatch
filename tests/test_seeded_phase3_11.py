"""Kill activation seed and the shrinking Phase 3 continuation."""

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
    "kill-cli-activation": ("phase3-continue-11",),
    "phase3-continue-12": ("kill-cli-activation",),
}
OWNERSHIP = {
    "kill-cli-activation": {
        "owns": ["tests/test_kill_cli_activation.py"],
        "hooks": ["squatch/daemon.py", "squatch/stages.py", "squatch/drain.py",
                  "squatch/__main__.py", "tests/test_kill_signal_journal.py"],
    },
    "phase3-continue-12": {
        "owns": ["tickets", "tests/test_seeded_phase3_12.py"], "hooks": [],
    },
}
CONTEXT = {
    "kill-cli-activation": (
        "squatch/daemon.py", "tests/test_kill_signal_journal.py",
        "tests/test_kill_executor_abort.py", "tests/test_kill_worker_stop.py",
        "tests/test_kill_failure_suppression.py", "tests/test_daemon_composition.py",
    ),
    "phase3-continue-12": (
        "tests/test_seeded_phase3_core.py", "squatch/daemon.py",
        "tests/test_daemon_tasks.py", "tests/test_control_cli.py",
        "tests/test_daemon_composition.py",
    ),
}
ON_DEMAND = {"squatch/stages.py", "squatch/drain.py", "squatch/__main__.py"}
PRESERVATION = (
    "tests/test_kill_executor_abort.py", "tests/test_kill_worker_stop.py",
    "tests/test_kill_failure_suppression.py", "tests/test_daemon_composition.py",
)
EXISTING_AT_AUTHORING = {
    "tests/test_seeded_phase3_core.py": 5877,
    "squatch/daemon.py": 11054,
    "squatch/stages.py": 52646,
    "squatch/drain.py": 24422,
    "squatch/__main__.py": 16076,
    "tests/test_kill_signal_journal.py": 2723,
    "tests/test_kill_executor_abort.py": 3882,
    "tests/test_kill_worker_stop.py": 5915,
    "tests/test_kill_failure_suppression.py": 5486,
    "tests/test_daemon_tasks.py": 6757,
    "tests/test_control_cli.py": 9688,
    "tests/test_daemon_composition.py": 21280,
}
NEW_PATH_OWNERS = {
    "tests/test_kill_cli_activation.py": "kill-cli-activation",
    "tests/test_seeded_phase3_12.py": "phase3-continue-12",
    "squatch/heartbeat.py": "heartbeat",
    "tests/test_heartbeat.py": "heartbeat",
    "tests/test_seeded_phase3_13.py": "phase3-continue-13",
}
FULL = (
    ("kill-cli-activation",), ("heartbeat",), ("restart-timers",),
    ("flake-detection", "flake-release"), ("journal-roll", "storm-ledger"),
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


def test_exact_seeds_edges_tiers_budgets_cap_fences_and_new_path_owners():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert tuple(BATCH) == ("kill-cli-activation", "phase3-continue-12")
    assert len(BATCH) <= config.seeding.max_seeds_per_admission == 3
    [contract] = [block["ownership"] for block in _yaml("phase3-continue-11")
                  if isinstance(block, dict) and "ownership" in block]
    assert contract == OWNERSHIP
    for stem, depends in BATCH.items():
        ticket = _ticket(stem)
        tiers = ("high", "high") if stem == "kill-cli-activation" else ("medium", "medium")
        assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
        assert ticket.depends == depends and ticket.plan_sections == ("20",)
        assert (ticket.agent_tier, ticket.agent_effort) == tiers
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
        assert ticket.stuck_minutes <= config.drain.max_ticket_minutes
        assert ticket.scope_fence == tuple(OWNERSHIP[stem]["owns"] + OWNERSHIP[stem]["hooks"])

    assert NEW_PATH_OWNERS == {
        "tests/test_kill_cli_activation.py": "kill-cli-activation",
        "tests/test_seeded_phase3_12.py": "phase3-continue-12",
        "squatch/heartbeat.py": "heartbeat", "tests/test_heartbeat.py": "heartbeat",
        "tests/test_seeded_phase3_13.py": "phase3-continue-13",
    }


def test_fence_classification_partition_and_predecessor_preservation():
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
            elif path in ON_DEMAND:
                assert stem == "kill-cli-activation"
            else:
                assert path in ticket.context, (stem, path)

    activation = _ticket("kill-cli-activation")
    assert ON_DEMAND.isdisjoint(activation.context)
    assert ON_DEMAND <= set(activation.scope_fence)
    assert set(PRESERVATION) <= set(activation.context)
    assert set(PRESERVATION).isdisjoint(activation.scope_fence)
    assert "tests/test_kill_signal_journal.py" in activation.scope_fence
    scope = _section("kill-cli-activation", "Scope in")
    criteria = _section("kill-cli-activation", "Acceptance criteria")
    assert "test_kill_boundary_is_dormant_and_not_a_cli_verb" in scope
    assert "Migrate only" in scope and "kill-verb absence assertion" in criteria
    assert "executor abort, worker stop, and failure suppression" in scope
    assert "first real serve task owner" in scope


def test_authoring_sizes_and_max_effort_headroom():
    assert {path: (REPO / path).stat().st_size for path in EXISTING_AT_AUTHORING} == \
        EXISTING_AT_AUTHORING
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


def test_continuation_repairs_heartbeat_ownership_and_context_contract():
    continuation = _ticket("phase3-continue-12")
    [ownership] = [block["ownership"] for block in _yaml("phase3-continue-12")
                   if isinstance(block, dict) and "ownership" in block]
    assert ownership == {
        "heartbeat": {"owns": ["squatch/heartbeat.py", "tests/test_heartbeat.py"],
                      "hooks": ["squatch/daemon.py"]},
        "phase3-continue-13": {"owns": ["tickets", "tests/test_seeded_phase3_13.py"],
                                "hooks": []},
    }
    assert continuation.context == CONTEXT["phase3-continue-12"]
    for section in ("Scope in", "Acceptance criteria"):
        text = _section("phase3-continue-12", section)
        for path in ("tests/test_daemon_tasks.py", "tests/test_control_cli.py",
                     "tests/test_daemon_composition.py"):
            assert path in text
    criteria = _section("phase3-continue-12", "Acceptance criteria")
    for phrase in ("every existing fence path is existing Context", "predecessor-test closure",
                   "authoring-time Context sizes", "max-effort render", "REQ_RENDER_HEADROOM"):
        assert phrase in criteria


def test_successor_removes_only_activation_and_starts_at_heartbeat():
    assert _admissions("phase3-continue-11") == FULL
    successor = _admissions("phase3-continue-12")
    assert successor == FULL[1:]
    assert successor[0] == ("heartbeat",)
    stems = [stem for row in successor for stem in row]
    assert len(stems) == len(set(stems))
    assert "kill-cli-activation" not in stems
