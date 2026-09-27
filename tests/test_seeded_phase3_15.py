"""Journal-roll and storm-ledger seed contracts."""

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
    "journal-roll": ("phase3-continue-15",),
    "storm-ledger": ("journal-roll",),
    "phase3-continue-16": ("journal-roll", "storm-ledger"),
}
OWNERSHIP = {
    "journal-roll": {"owns": ["tests/test_journal_roll.py"], "hooks": ["squatch/journal.py"]},
    "storm-ledger": {"owns": ["squatch/storm.py", "tests/test_storm.py"], "hooks": []},
    "phase3-continue-16": {"owns": ["tickets", "tests/test_seeded_phase3_16.py"], "hooks": []},
}
CONTEXT = {
    "journal-roll": ("squatch/journal.py", "tests/test_journal.py"),
    "storm-ledger": ("squatch/journal.py", "tests/test_journal.py"),
    "phase3-continue-16": (
        "tests/test_seeded_phase3_11.py", "squatch/box.py", "squatch/daemon.py",
        "squatch/__main__.py", "tests/test_box.py", "tests/test_daemon_composition.py",
    ),
}
EXISTING_AT_AUTHORING = {
    "tests/test_seeded_phase3_11.py": 9238,
    "squatch/journal.py": 7110,
    "tests/test_journal.py": 9535,
    "squatch/box.py": 12324,
    "squatch/daemon.py": 15521,
    "squatch/__main__.py": 17521,
    "tests/test_box.py": 8419,
    "tests/test_daemon_composition.py": 21280,
}
PLAN_SECTION_AT_AUTHORING = 20430
NEW_PATH_OWNERS = {
    "squatch/restart.py": "restart-timers", "squatch/timers.py": "restart-timers",
    "tests/test_restart_timers.py": "restart-timers", "squatch/flake.py": "flake-detection",
    "tests/test_flake.py": "flake-detection", "tests/test_seeded_phase3_14.py": "phase3-continue-14",
    "tests/test_seeded_phase3_15.py": "phase3-continue-15",
    "tests/test_journal_roll.py": "journal-roll", "squatch/storm.py": "storm-ledger",
    "tests/test_storm.py": "storm-ledger", "tests/test_seeded_phase3_16.py": "phase3-continue-16",
    "tests/test_storm_producer.py": "storm-producer-wiring",
    "tests/test_storm_notification_activation.py": "storm-notification-activation",
    "tests/test_seeded_phase3_17.py": "phase3-continue-17",
}
PRESERVATION = ("tests/test_journal.py",)
FULL = (
    ("journal-roll", "storm-ledger"),
    ("storm-producer-wiring", "storm-notification-activation"),
    ("storm-dispatch-hold",), ("checkpoint-push",), ("daemon-soak",),
    ("soak-run",), ("phase3-exit",),
)
SIBLING_NEW = {
    "tests/test_storm_producer.py", "tests/test_storm_notification_activation.py",
    "tests/test_seeded_phase3_17.py",
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
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


def _yaml(stem):
    return [yaml.safe_load(block) for block in re.findall(
        r"```yaml\n(.*?)\n```", _section(stem, "Scope in"), re.S)]


def _admissions(stem):
    [rows] = [block for block in _yaml(stem) if isinstance(block, list)]
    return tuple(tuple(row) for row in rows)


def test_exact_seeds_edges_tiers_budgets_cap_fences_context_and_owners():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert tuple(BATCH) == ("journal-roll", "storm-ledger", "phase3-continue-16")
    assert len(BATCH) == config.seeding.max_seeds_per_admission == 3
    [contract] = [block["ownership"] for block in _yaml("phase3-continue-15")
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
    from test_seeded_phase3_14 import NEW_PATH_OWNERS as predecessor_owners
    assert {path: NEW_PATH_OWNERS[path] for path in predecessor_owners} == predecessor_owners
    for path, owner in NEW_PATH_OWNERS.items():
        if owner in BATCH:
            assert path in _ticket(owner).scope_fence


def test_context_partition_sizes_fences_and_predecessor_preservation():
    sibling_new = {path for path, owner in NEW_PATH_OWNERS.items() if owner in BATCH}
    assert set(EXISTING_AT_AUTHORING) == set().union(*map(set, CONTEXT.values()))
    for stem in BATCH:
        ticket = _ticket(stem)
        assert set(ticket.context).isdisjoint(sibling_new)
        assert set(ticket.context).isdisjoint({"squatch/specs.py", "specs/implement.md"})
        for path in ticket.context:
            assert (REPO / path).is_file()
            assert path in EXISTING_AT_AUTHORING
            assert DATA_MARKER not in (REPO / path).read_text()
        for path in ticket.scope_fence:
            if path == "tickets" or NEW_PATH_OWNERS.get(path) == stem:
                continue
            assert path in ticket.context, (stem, path)
    for stem in ("journal-roll", "storm-ledger"):
        assert set(PRESERVATION) <= set(_ticket(stem).context)
        assert set(PRESERVATION).isdisjoint(_ticket(stem).scope_fence)
        assert "read-only preservation" in _section(stem, "Scope in")
        assert "unchanged" in _section(stem, "Scope in")


def test_roll_storm_and_successor_boundaries_are_specific_and_separate():
    roll, storm = _section("journal-roll", "Scope in"), _section("storm-ledger", "Scope in")
    for phrase in ("64 MiB", "24h", "ordered", "immutable", "replay across rolled segments"):
        assert phrase in roll
    for phrase in (
        "`storm-occurrence/<signature>/<occurrence_id>`", "`signal`",
        "{kind: storm_occurrence, signature, occurrence_id, emitting_stage}",
        "idempotent", "cross-segment", "`K=5`", "`T=1 hour`", "lower boundary",
        "AST transitive `squatch.*` import-closure", "`squatch/__main__.py`",
        "no trip signal, box message, notification, producer wiring, or dispatch hold",
    ):
        assert phrase in storm
    scope = _section("phase3-continue-16", "Scope in")
    criteria = _section("phase3-continue-16", "Acceptance criteria")
    for phrase in (
        "then-existing `squatch/storm.py` and `tests/test_storm.py` Context",
        "stable occurrence identity", "signature-dedup hit", "production composition remains dormant",
        "deterministic over `(signature, first_live_occurrence_id, crossing_occurrence_id)`",
        "replay cannot mint a second trip", "P0 `failure_report`", "Dispatch suppression stays",
        "`PRESERVATION` set", "authoring-time Context sizes", "`REQ_RENDER_HEADROOM`",
    ):
        assert phrase in scope
    assert "`squatch/__main__.py`" in scope and "sibling-new paths" in criteria
    assert not any(path in _section("phase3-continue-16", "Context") for path in SIBLING_NEW)
    [ownership] = [block["ownership"] for block in _yaml("phase3-continue-16")
                   if isinstance(block, dict) and "ownership" in block]
    assert "squatch/__main__.py" in ownership["storm-notification-activation"]["hooks"]


def test_successor_removes_only_journal_and_storm_pair_without_combining():
    assert _admissions("phase3-continue-15") == FULL
    successor = _admissions("phase3-continue-16")
    assert successor == FULL[1:]
    assert successor[0] == ("storm-producer-wiring", "storm-notification-activation")
    stems = [stem for row in successor for stem in row]
    assert len(stems) == len(set(stems)) and set(FULL[0]).isdisjoint(stems)


def test_authoring_section_length_and_max_effort_headroom():
    plan = (REPO / PLAN_FILE).read_text()
    section = plan.split("## 20. Open decisions", 1)[1].split("## 21.", 1)[0]
    assert PLAN_SECTION_AT_AUTHORING == 20430
    spec = load_spec(REPO / "specs" / "implement.md")
    limit = int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
    for stem in BATCH:
        context = "".join(f"### {path}\n{'x' * EXISTING_AT_AUTHORING[path]}\n" for path in CONTEXT[stem])
        workspace = f"stem: {stem}\nbranch: {stem}\nrun record: tickets/{stem}/{RUN_RECORD}\n"
        rendered = spec.render({"workspace": DataBlock("engine", workspace),
                                "ticket": DataBlock("host", _path(stem).read_text()),
                                "context": DataBlock("host", context)}, plan=plan,
                               plan_sections=("20",), effort="max")
        historical_length = len(rendered) - max(0, len(section) - PLAN_SECTION_AT_AUTHORING)
        assert historical_length <= limit, (stem, historical_length, limit)
