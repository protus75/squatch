"""Worker/failure kill seeds and the singleton activation continuation."""

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
    "kill-worker-stop": ("phase3-continue-10",),
    "kill-failure-suppression": ("kill-worker-stop",),
    "phase3-continue-11": ("kill-worker-stop", "kill-failure-suppression"),
}
PRESERVATION = (
    "tests/test_kill_executor_abort.py", "tests/test_kill_signal_journal.py",
    "tests/test_daemon_tasks.py",
)
CONTEXT = {
    "kill-worker-stop": ("squatch/daemon.py", *PRESERVATION),
    "kill-failure-suppression": ("squatch/daemon.py", *PRESERVATION),
    "phase3-continue-11": (
        "tests/test_seeded_phase3_core.py", "squatch/daemon.py",
        "tests/test_kill_signal_journal.py", "tests/test_kill_executor_abort.py",
        "tests/test_kill_worker_stop.py", "tests/test_kill_failure_suppression.py",
        "tests/test_daemon_tasks.py", "tests/test_control_cli.py",
        "tests/test_daemon_composition.py",
    ),
}
OWNERSHIP = {
    "kill-worker-stop": {"owns": ["tests/test_kill_worker_stop.py"],
                         "hooks": ["squatch/daemon.py"]},
    "kill-failure-suppression": {"owns": ["tests/test_kill_failure_suppression.py"],
                                 "hooks": ["squatch/daemon.py"]},
    "phase3-continue-11": {"owns": ["tickets", "tests/test_seeded_phase3_11.py"],
                           "hooks": []},
}
# Historical render fixtures must not grow with later production edits.
EXISTING_AT_AUTHORING = {
    "squatch/daemon.py": 11054,
    "tests/test_seeded_phase3_core.py": 5877,
    "tests/test_kill_executor_abort.py": 3882,
    "tests/test_kill_signal_journal.py": 2723,
    "tests/test_kill_worker_stop.py": 5915,
    "tests/test_kill_failure_suppression.py": 5486,
    "tests/test_daemon_tasks.py": 6757,
    "tests/test_control_cli.py": 9688,
    "tests/test_daemon_composition.py": 21280,
}
NEW_PATH_OWNERS = {
    "tests/test_kill_worker_stop.py": "kill-worker-stop",
    "tests/test_kill_failure_suppression.py": "kill-failure-suppression",
    "tests/test_seeded_phase3_11.py": "phase3-continue-11",
}
FULL = (
    ("kill-worker-stop", "kill-failure-suppression"), ("kill-cli-activation",),
    ("heartbeat",), ("restart-timers",), ("flake-detection", "flake-release"),
    ("journal-roll", "storm-ledger"),
    ("storm-producer-wiring", "storm-notification-activation"),
    ("storm-dispatch-hold",), ("checkpoint-push",), ("daemon-soak",),
    ("soak-run",), ("phase3-exit",),
)
ACTIVATION_OWNERSHIP = {
    "kill-cli-activation": {
        "owns": ["tests/test_kill_cli_activation.py"],
        "hooks": ["squatch/daemon.py", "squatch/stages.py", "squatch/drain.py",
                  "squatch/__main__.py", "tests/test_kill_signal_journal.py"],
    },
    "phase3-continue-12": {"owns": ["tickets", "tests/test_seeded_phase3_12.py"],
                           "hooks": []},
}


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


def test_exact_seeds_edges_tiers_budgets_and_cap():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert tuple(BATCH) == ("kill-worker-stop", "kill-failure-suppression",
                            "phase3-continue-11")
    assert len(BATCH) == config.seeding.max_seeds_per_admission == 3
    for stem, depends in BATCH.items():
        ticket = _ticket(stem)
        assert (ticket.source, ticket.priority) == ("seed", "P1")
        assert ticket.state in {"confirmed", "rejected"}
        assert ticket.depends == depends
        assert ticket.plan_sections == ("20",)
        assert (ticket.agent_tier, ticket.agent_effort) == ("medium", "medium")
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
        assert ticket.stuck_minutes <= config.drain.max_ticket_minutes


def test_owns_then_hooks_fences_existing_context_and_new_path_owners():
    [contract] = [block["ownership"] for block in _yaml("phase3-continue-10")
                  if isinstance(block, dict) and "ownership" in block]
    assert contract == OWNERSHIP
    for stem in BATCH:
        ticket = _ticket(stem)
        assert ticket.scope_fence == tuple(OWNERSHIP[stem]["owns"] + OWNERSHIP[stem]["hooks"])
        assert ticket.context == CONTEXT[stem]
        assert set(ticket.context) <= set(EXISTING_AT_AUTHORING)
        if stem != "phase3-continue-11":
            assert set(ticket.context).isdisjoint(NEW_PATH_OWNERS)
        assert set(ticket.context).isdisjoint({"squatch/specs.py", "specs/implement.md"})
        for path in ticket.scope_fence:
            if path in NEW_PATH_OWNERS:
                assert NEW_PATH_OWNERS[path] == stem
            elif path in EXISTING_AT_AUTHORING:
                assert path in ticket.context
            elif path != "tickets":
                raise AssertionError(f"unclassified fence path: {path}")
        if stem != "phase3-continue-11":
            assert _yaml(stem) == [{"ownership": {stem: OWNERSHIP[stem]}}]
            assert "squatch/__main__.py" not in ticket.scope_fence
    assert {path: stem for stem, record in OWNERSHIP.items()
            for path in record["owns"] if path != "tickets"} == NEW_PATH_OWNERS


def test_predecessor_suites_are_read_only_and_verified():
    for stem in ("kill-worker-stop", "kill-failure-suppression"):
        ticket = _ticket(stem)
        verified = set(re.findall(r"tests/[\w_]+\.py", _section(stem, "Verification")))
        assert set(PRESERVATION) <= set(ticket.context)
        assert set(PRESERVATION).isdisjoint(ticket.scope_fence)
        expected = set(PRESERVATION) | {"tests/test_kill_worker_stop.py"}
        if stem == "kill-failure-suppression":
            expected.add("tests/test_kill_failure_suppression.py")
        assert verified == expected


def test_activation_predecessor_closure_and_read_only_harness_requirement():
    [contract] = [block for block in _yaml("phase3-continue-11") if isinstance(block, dict)]
    assert contract["ownership"] == ACTIVATION_OWNERSHIP
    assert contract["read_only_context"] == {
        "kill-cli-activation": [
            "tests/test_kill_executor_abort.py", "tests/test_kill_worker_stop.py",
            "tests/test_kill_failure_suppression.py", "tests/test_daemon_composition.py",
        ],
    }
    activation = contract["ownership"]["kill-cli-activation"]
    read_only = contract["read_only_context"]["kill-cli-activation"]
    assert set(read_only).isdisjoint(activation["owns"] + activation["hooks"])
    assert set(read_only) <= set(_ticket("phase3-continue-11").context)
    # The obligation appears in both the authoring scope and acceptance surface.
    for section in ("Scope in", "Acceptance criteria"):
        paths = re.findall(r"tests/[\w_]+\.py", _section("phase3-continue-11", section))
        assert "tests/test_daemon_composition.py" in paths
    assert {"squatch/stages.py", "squatch/drain.py", "squatch/__main__.py"}.isdisjoint(
        _ticket("phase3-continue-11").context)


def test_successor_removes_only_the_head_admission():
    assert _admissions("phase3-continue-10") == FULL
    successor = _admissions("phase3-continue-11")
    assert successor == FULL[1:]
    assert successor[0] == ("kill-cli-activation",)
    assert successor[1] == ("heartbeat",)
    stems = [stem for row in successor for stem in row]
    assert len(stems) == len(set(stems))
    assert set(stems).isdisjoint(FULL[0])


def test_max_effort_renders_fit_with_pinned_authoring_material():
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
