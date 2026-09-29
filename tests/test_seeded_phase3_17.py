"""Production storm-hold and checkpoint-continuation seed contracts."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import DATA_MARKER, RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket


REPO = Path(__file__).resolve().parent.parent
BATCH = {
    "storm-dispatch-hold": ("phase3-continue-17",),
    "phase3-continue-18": ("storm-dispatch-hold",),
}
OWNERSHIP = {
    "storm-dispatch-hold": {
        "owns": ["tests/test_storm_hold.py"],
        "hooks": ["squatch/storm.py", "squatch/control.py", "squatch/daemon.py",
                  "squatch/drain.py", "squatch/__main__.py", "tests/test_storm.py",
                  "tests/test_storm_producer.py", "tests/test_storm_notification_activation.py"],
    },
    "phase3-continue-18": {"owns": ["tickets", "tests/test_seeded_phase3_18.py"], "hooks": []},
}
CONTEXT = {
    "storm-dispatch-hold": (
        "squatch/storm.py", "squatch/control.py", "squatch/daemon.py", "tests/test_storm.py",
        "tests/test_storm_producer.py", "tests/test_storm_notification_activation.py",
        "tests/test_daemon_composition.py",
    ),
    "phase3-continue-18": ("tests/test_seeded_phase3_11.py", "tests/test_daemon_composition.py"),
}
ON_DEMAND = {"squatch/drain.py", "squatch/__main__.py"}
PRESERVATION = ("tests/test_daemon_composition.py",)
EXISTING_AT_AUTHORING = {
    "tests/test_seeded_phase3_11.py": 9238,
    "squatch/storm.py": 5814,
    "squatch/control.py": 10215,
    "squatch/daemon.py": 17267,
    "squatch/drain.py": 25282,
    "squatch/__main__.py": 17946,
    "tests/test_storm.py": 5662,
    "tests/test_storm_producer.py": 9633,
    "tests/test_storm_notification_activation.py": 12963,
    "tests/test_daemon_composition.py": 21280,
}
PLAN_SECTION_AT_AUTHORING = 24350
NEW_PATH_OWNERS = {
    "tests/test_storm_hold.py": "storm-dispatch-hold",
    "tests/test_seeded_phase3_18.py": "phase3-continue-18",
    "squatch/checkpoint.py": "checkpoint-push",
    "tests/test_checkpoint.py": "checkpoint-push",
    "tests/test_seeded_phase3_19.py": "phase3-continue-19",
}
FULL = (("storm-dispatch-hold",), ("checkpoint-push",), ("daemon-soak",),
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


def _phrases(stem, section, phrases):
    text = _section(stem, section)
    for phrase in phrases:
        assert phrase in text, (stem, section, phrase)


def test_exact_seeds_edges_tiers_budgets_cap_fences_context_and_registry_owners():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert tuple(BATCH) == ("storm-dispatch-hold", "phase3-continue-18")
    assert len(BATCH) <= config.seeding.max_seeds_per_admission == 3
    [contract] = [block["ownership"] for block in _yaml("phase3-continue-17")
                  if isinstance(block, dict) and "ownership" in block]
    assert contract == OWNERSHIP
    for stem, depends in BATCH.items():
        ticket = _ticket(stem)
        tiers = ("high", "high") if stem == "storm-dispatch-hold" else ("medium", "medium")
        assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
        assert ticket.depends == depends and ticket.plan_sections == ("20",)
        assert (ticket.agent_tier, ticket.agent_effort) == tiers
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
        assert ticket.stuck_minutes <= config.drain.max_ticket_minutes
        assert ticket.scope_fence == tuple(OWNERSHIP[stem]["owns"] + OWNERSHIP[stem]["hooks"])
        assert ticket.context == CONTEXT[stem]

    hold = _ticket("storm-dispatch-hold")
    continuation = _ticket("phase3-continue-18")
    [future_ownership] = [block["ownership"] for block in _yaml("phase3-continue-18")
                          if isinstance(block, dict) and "ownership" in block]
    for path, owner in NEW_PATH_OWNERS.items():
        if owner == "storm-dispatch-hold":
            owns = hold.scope_fence
        elif owner == "phase3-continue-18":
            owns = continuation.scope_fence
        else:
            owns = future_ownership[owner]["owns"]
        assert path in owns, (path, owner)
        assert all(path not in ticket.context for ticket in (hold, continuation))


def test_context_partition_predecessor_migration_preservation_and_on_demand_roots():
    hold = _ticket("storm-dispatch-hold")
    assert set(hold.context) <= set(EXISTING_AT_AUTHORING)
    assert set(hold.context).isdisjoint(ON_DEMAND | set(NEW_PATH_OWNERS) | {"squatch/specs.py", "specs/implement.md"})
    for path in hold.context:
        assert (REPO / path).is_file() and DATA_MARKER not in (REPO / path).read_text()
    for path in hold.scope_fence:
        if path not in ON_DEMAND and path not in NEW_PATH_OWNERS:
            assert path in hold.context, path
    assert ON_DEMAND <= set(hold.scope_fence) and ON_DEMAND.isdisjoint(hold.context)
    assert set(PRESERVATION) <= set(hold.context) and set(PRESERVATION).isdisjoint(hold.scope_fence)
    predecessors = {"tests/test_storm.py", "tests/test_storm_producer.py", "tests/test_storm_notification_activation.py"}
    assert predecessors <= set(hold.context) & set(hold.scope_fence)
    _phrases("storm-dispatch-hold", "Scope in", [
        "dispatch-absence assertions", "exact occurrence/trip body, key-set, and `_event` fixture assertions",
        "Retain occurrence identity, trip-id, report", "read-only preservation Context", "remains unchanged",
    ])
    continuation = _ticket("phase3-continue-18")
    assert continuation.context == CONTEXT["phase3-continue-18"]
    assert "tests/test_seeded_phase3_17.py" not in continuation.context


def test_hold_contract_selects_origin_before_accounting_and_owns_real_resume_recovery():
    _phrases("storm-dispatch-hold", "Scope in", [
        "always present as a string or null", "validated like `emitting_stage`",
        "optional argument defaulting to None", "legacy occurrence and trip events lacking it as None",
        "producer supplies the Box message origin", "emitting_stage` stays diagnostic",
        "never the selector", "stem equals the tripped `emitting_origin`",
        "before retry-cap draws or any other durable dispatch accounting", "Other stems remain eligible",
        "null and non-ticket origins create no global hold", "Journal a hold decision before its mutation",
        "identity-bound exactly once", "current-lifecycle control inbox", "stale lifecycle, pre-trip, and wrong-hold",
        "Rehydrate unreleased storm holds after restart", "manual-pause and merge-admission holds",
        "live drain's CLI composition root", "no later admission activates the hold", "production owner",
    ])
    _phrases("storm-dispatch-hold", "Scope out", ["defer production activation"])
    _phrases("storm-dispatch-hold", "Acceptance criteria", [
        "per-stem hold is bound through the live drain's CLI composition root",
        "drain assembled through that root suppresses the tripped stem and resumes it",
    ])


def test_successor_removes_only_hold_and_has_exact_suffix():
    assert _admissions("phase3-continue-17") == FULL
    successor = _admissions("phase3-continue-18")
    assert successor == FULL[1:] and successor[0] == ("checkpoint-push",)
    stems = [stem for row in successor for stem in row]
    assert len(stems) == len(set(stems)) and "storm-dispatch-hold" not in stems


def test_authoring_sizes_section_length_and_every_max_effort_render():
    assert PLAN_SECTION_AT_AUTHORING == 24350
    spec = load_spec(REPO / "specs" / "implement.md")
    plan = (REPO / PLAN_FILE).read_text()
    start = plan.index("## 20.")
    body = plan.index("\n", start) + 1
    end = plan.index("\n## ", body) + 1
    plan = plan[:body] + "x" * (PLAN_SECTION_AT_AUTHORING - 1) + "\n" + plan[end:]
    limit = int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
    for stem in BATCH:
        context = "".join(f"### {path}\n{'x' * EXISTING_AT_AUTHORING[path]}\n" for path in CONTEXT[stem])
        workspace = f"stem: {stem}\nbranch: {stem}\nrun record: tickets/{stem}/{RUN_RECORD}\n"
        rendered = spec.render({"workspace": DataBlock("engine", workspace),
                                "ticket": DataBlock("host", _path(stem).read_text()),
                                "context": DataBlock("host", context)}, plan=plan,
                               plan_sections=("20",), effort="max")
        assert len(rendered) <= limit, (stem, len(rendered), limit)
