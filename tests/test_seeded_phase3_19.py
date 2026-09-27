"""Daemon-soak and terminal-continuation seed contracts."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import DATA_MARKER, RENDER_BOUND_CHARS, DataBlock, load_spec, resolve_plan_sections
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket


REPO = Path(__file__).resolve().parent.parent
BATCH = {
    "daemon-soak": ("phase3-continue-19",),
    "phase3-continue-20": ("daemon-soak",),
}
OWNERSHIP = {
    "daemon-soak": {
        "owns": ["eval/daemon_soak.py", "tests/test_daemon_soak.py"],
        "hooks": ["squatch/artifacts.py", "squatch/stages.py"],
    },
    "phase3-continue-20": {
        "owns": ["tickets", "tests/test_seeded_phase3_20.py"], "hooks": [],
    },
}
CONTEXT = {
    "daemon-soak": ("squatch/artifacts.py", "squatch/stages.py"),
    "phase3-continue-20": (
        "tests/test_seeded_phase3_11.py", "tests/test_daemon_composition.py",
    ),
}
EXISTING_AT_AUTHORING = {
    "squatch/artifacts.py": 3672,
    "squatch/stages.py": 52818,
    "tests/test_seeded_phase3_11.py": 9238,
    "tests/test_daemon_composition.py": 21280,
}
PLAN_SECTION_AT_AUTHORING = 24350
NEW_PATH_OWNERS = {
    "eval/daemon_soak.py": "daemon-soak",
    "tests/test_daemon_soak.py": "daemon-soak",
    "tests/test_seeded_phase3_20.py": "phase3-continue-20",
    "squatch/serve.py": "serve-activation",
    "tests/test_serve.py": "serve-activation",
    "tests/test_seeded_phase3_21.py": "phase3-continue-21",
}
FUTURE_OWNERSHIP = {
    "serve-activation": {
        "owns": [
            "squatch/serve.py", "squatch/daemon.py", "squatch/__main__.py",
            "tests/test_serve.py", "tests/test_daemon_composition.py",
            "tests/test_daemon_tasks.py", "tests/test_kill_worker_stop.py",
            "tests/test_kill_failure_suppression.py",
        ],
        "hooks": [],
    },
    "phase3-continue-21": {
        "owns": ["tickets", "tests/test_seeded_phase3_21.py"], "hooks": [],
    },
}
FUTURE_CONTEXT = {
    "serve-activation": (
        "tests/test_daemon_composition.py", "tests/test_daemon_tasks.py",
        "tests/test_kill_worker_stop.py", "tests/test_kill_failure_suppression.py",
    ),
    "phase3-continue-21": (
        "tests/test_seeded_phase3_11.py", "tests/test_daemon_composition.py",
    ),
}
ORIGINAL_FULL = (("daemon-soak",), ("soak-run",), ("phase3-exit",))
CORRECTED_SUFFIX = (
    ("serve-activation",), ("daemon-soak-runner",),
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
    assert tuple(BATCH) == ("daemon-soak", "phase3-continue-20")
    assert len(BATCH) <= config.seeding.max_seeds_per_admission == 3
    [contract] = [block["ownership"] for block in _yaml("phase3-continue-19")
                  if isinstance(block, dict) and "ownership" in block]
    assert contract == OWNERSHIP
    for stem, depends in BATCH.items():
        ticket = _ticket(stem)
        tiers = ("high", "high") if stem == "daemon-soak" else ("medium", "medium")
        assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
        assert ticket.depends == depends and ticket.plan_sections == ("20",)
        assert (ticket.agent_tier, ticket.agent_effort) == tiers
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
        assert ticket.stuck_minutes <= config.drain.max_ticket_minutes
        assert ticket.scope_fence == tuple(OWNERSHIP[stem]["owns"] + OWNERSHIP[stem]["hooks"])
        assert ticket.context == CONTEXT[stem]

    [future] = [block["ownership"] for block in _yaml("phase3-continue-20")
                if isinstance(block, dict) and "ownership" in block]
    assert future == FUTURE_OWNERSHIP
    for path, owner in NEW_PATH_OWNERS.items():
        contract = OWNERSHIP[owner] if owner in OWNERSHIP else FUTURE_OWNERSHIP[owner]
        assert path in contract["owns"]


def test_context_partition_existing_fences_and_predecessor_closure():
    sibling_new = set(NEW_PATH_OWNERS)
    for stem in BATCH:
        ticket = _ticket(stem)
        assert set(ticket.context) <= set(EXISTING_AT_AUTHORING)
        assert set(ticket.context).isdisjoint(sibling_new | {"squatch/specs.py", "specs/implement.md"})
        for path in ticket.context:
            assert (REPO / path).is_file() and DATA_MARKER not in (REPO / path).read_text()
        for path in ticket.scope_fence:
            if path != "tickets" and path not in sibling_new:
                assert path in ticket.context, (stem, path)

    soak = _ticket("daemon-soak")
    assert set(soak.scope_fence) - {"eval/daemon_soak.py", "tests/test_daemon_soak.py"} == set(soak.context)
    assert not (set(soak.context) & {"tests/test_seeded_phase3_19.py", "squatch/specs.py"})
    continuation = _ticket("phase3-continue-20")
    assert continuation.context == CONTEXT["phase3-continue-20"]
    assert "tests/test_seeded_phase3_19.py" not in continuation.context
    scope = _section("daemon-soak", "Scope in")
    assert "predecessor-test closure Context" in scope and "no predecessor test requires migration" in scope


def test_authoring_sizes_section_length_and_max_effort_headroom():
    assert PLAN_SECTION_AT_AUTHORING == 24350
    spec = load_spec(REPO / "specs" / "implement.md")
    plan = (REPO / PLAN_FILE).read_text()
    section = resolve_plan_sections(plan, ("20",))[0][1]
    limit = int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
    for stem in BATCH:
        context = "".join(f"### {path}\n{'x' * EXISTING_AT_AUTHORING[path]}\n"
                          for path in CONTEXT[stem])
        workspace = f"stem: {stem}\nbranch: {stem}\nrun record: tickets/{stem}/{RUN_RECORD}\n"
        rendered = spec.render({"workspace": DataBlock("engine", workspace),
                                "ticket": DataBlock("host", _path(stem).read_text()),
                                "context": DataBlock("host", context)}, plan=plan,
                               plan_sections=("20",), effort="max")
        historical_length = len(rendered) - len(section) + PLAN_SECTION_AT_AUTHORING
        assert historical_length <= limit, (stem, historical_length, limit)


def test_corrective_continuation_pins_serve_and_soak_runner_contract():
    continuation = _ticket("phase3-continue-20")
    assert continuation.depends == ("daemon-soak",)
    scope = _section("phase3-continue-20", "Scope in")
    assert _admissions("phase3-continue-20") == CORRECTED_SUFFIX
    assert "`serve-activation` depends on `phase3-continue-20` and `daemon-soak`" in scope
    assert "is KNOWN-DEEP high/high" in scope
    assert "`phase3-continue-21` depends on `serve-activation`" in scope
    assert "is medium/medium with 75m/150m budgets" in scope
    assert "cap 3" in scope
    assert "adds the `serve` verb and production continuous loop" in scope
    assert "activates worker-stop and kill-failure-suppression" in scope
    assert "`squatch/daemon.py` and `squatch/__main__.py` are fenced on-demand inspection exceptions" in scope
    assert "authors `daemon-soak-runner` alone plus `phase3-continue-22`" in scope
    assert "drives the merged production serve composition through injected seams" in scope
    assert "`phase3-continue-23` authors KNOWN-HARD high/high `phase3-exit` alone and no successor" in scope
    [future_context] = [block["context"] for block in _yaml("phase3-continue-20")
                        if isinstance(block, dict) and "context" in block]
    assert {stem: tuple(paths) for stem, paths in future_context.items()} == FUTURE_CONTEXT
    assert "squatch/specs.py" not in continuation.context


def test_plan_correction_inserts_missing_serve_and_runner_suffix():
    assert _admissions("phase3-continue-19") == ORIGINAL_FULL
    successor = _admissions("phase3-continue-20")
    assert successor == CORRECTED_SUFFIX and successor[0] == ("serve-activation",)
    stems = [stem for row in successor for stem in row]
    assert len(stems) == len(set(stems)) and "daemon-soak" not in stems
