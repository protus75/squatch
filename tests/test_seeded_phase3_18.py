"""Checkpoint-push and daemon-soak continuation seed contracts."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import DATA_MARKER, RENDER_BOUND_CHARS, DataBlock, load_spec, resolve_plan_sections
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket


REPO = Path(__file__).resolve().parent.parent
BATCH = {"checkpoint-push": ("phase3-continue-18",),
         "phase3-continue-19": ("checkpoint-push",)}
OWNERSHIP = {
    "checkpoint-push": {"owns": ["squatch/checkpoint.py", "tests/test_checkpoint.py"],
                        "hooks": ["squatch/daemon.py", "squatch/git.py", "tests/test_git.py",
                                  "tests/test_mergequeue.py"]},
    "phase3-continue-19": {"owns": ["tickets", "tests/test_seeded_phase3_19.py"], "hooks": []},
}
CONTEXT = {
    "checkpoint-push": ("squatch/daemon.py", "squatch/git.py", "tests/test_git.py"),
    "phase3-continue-19": ("tests/test_seeded_phase3_11.py", "tests/test_daemon_composition.py"),
}
EXISTING_AT_AUTHORING = {
    "squatch/daemon.py": 19849, "squatch/git.py": 7831, "tests/test_git.py": 14833,
    "tests/test_seeded_phase3_11.py": 9238, "tests/test_daemon_composition.py": 21280,
}
PLAN_SECTION_AT_AUTHORING = 24350
NEW_PATH_OWNERS = {
    "squatch/checkpoint.py": "checkpoint-push", "tests/test_checkpoint.py": "checkpoint-push",
    "tests/test_seeded_phase3_19.py": "phase3-continue-19",
    "eval/daemon_soak.py": "daemon-soak", "tests/test_daemon_soak.py": "daemon-soak",
    "tests/test_seeded_phase3_20.py": "phase3-continue-20",
}
FULL = (("checkpoint-push",), ("daemon-soak",), ("soak-run",), ("phase3-exit",))
CHECKPOINT_ON_DEMAND = {"tests/test_mergequeue.py"}


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


def test_exact_seeds_edges_tiers_budgets_cap_fences_context_and_registry_owners():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert tuple(BATCH) == ("checkpoint-push", "phase3-continue-19")
    assert len(BATCH) <= config.seeding.max_seeds_per_admission == 3
    [contract] = [block["ownership"] for block in _yaml("phase3-continue-18")
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
        assert ticket.context == CONTEXT[stem]
    [future] = [block["ownership"] for block in _yaml("phase3-continue-19")
                if isinstance(block, dict) and "ownership" in block]
    for path, owner in NEW_PATH_OWNERS.items():
        owner_contract = OWNERSHIP[owner] if owner in OWNERSHIP else future[owner]
        assert path in owner_contract["owns"]


def test_context_partition_and_checkpoint_contract():
    for stem in BATCH:
        ticket = _ticket(stem)
        assert set(ticket.context) <= set(EXISTING_AT_AUTHORING)
        assert set(ticket.context).isdisjoint(set(NEW_PATH_OWNERS) | {"squatch/specs.py", "specs/implement.md"})
        for path in ticket.context:
            assert (REPO / path).is_file() and DATA_MARKER not in (REPO / path).read_text()
        for path in ticket.scope_fence:
            if path != "tickets" and path not in NEW_PATH_OWNERS and path not in CHECKPOINT_ON_DEMAND:
                assert path in ticket.context, (stem, path)
    checkpoint = _section("checkpoint-push", "Scope in")
    for phrase in ("public argv-only Git push", "composition calls only that seam",
                   "re-fires an incomplete push after restart", "duplicating a completed push",
                   "test_git_conflict_seams_are_only_additions_and_old_rebase_still_aborts",
                   "fenced on-demand inspection exception", "public-operation allowlist"):
        assert phrase in checkpoint
    checkpoint_ticket = _ticket("checkpoint-push")
    assert CHECKPOINT_ON_DEMAND <= set(checkpoint_ticket.scope_fence)
    assert CHECKPOINT_ON_DEMAND.isdisjoint(checkpoint_ticket.context)
    continuation = _ticket("phase3-continue-19")
    assert "tests/test_seeded_phase3_18.py" not in continuation.context
    assert continuation.context == CONTEXT["phase3-continue-19"]


def test_authoring_sizes_section_length_and_max_effort_headroom():
    assert PLAN_SECTION_AT_AUTHORING == 24350
    spec = load_spec(REPO / "specs" / "implement.md")
    plan = (REPO / PLAN_FILE).read_text()
    section = resolve_plan_sections(plan, ("20",))[0][1]
    limit = int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
    for stem in BATCH:
        context = "".join(f"### {path}\n{'x' * EXISTING_AT_AUTHORING[path]}\n" for path in CONTEXT[stem])
        workspace = f"stem: {stem}\nbranch: {stem}\nrun record: tickets/{stem}/{RUN_RECORD}\n"
        rendered = spec.render({"workspace": DataBlock("engine", workspace),
                                "ticket": DataBlock("host", _path(stem).read_text()),
                                "context": DataBlock("host", context)}, plan=plan,
                               plan_sections=("20",), effort="max")
        assert len(rendered) - len(section) + PLAN_SECTION_AT_AUTHORING <= limit


def test_successor_removes_only_checkpoint_push_and_has_exact_suffix():
    assert _admissions("phase3-continue-18") == FULL
    successor = _admissions("phase3-continue-19")
    assert successor == FULL[1:] and successor[0] == ("daemon-soak",)
    stems = [stem for row in successor for stem in row]
    assert len(stems) == len(set(stems)) and "checkpoint-push" not in stems
