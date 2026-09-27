"""Storm producer/notification seeds and the production-hold continuation."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import (DATA_MARKER, RENDER_BOUND_CHARS, DataBlock, load_spec,
                           resolve_plan_sections)
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket


REPO = Path(__file__).resolve().parent.parent
BATCH = {
    "storm-producer-wiring": ("phase3-continue-16",),
    "storm-notification-activation": ("storm-producer-wiring",),
    "phase3-continue-17": ("storm-producer-wiring", "storm-notification-activation"),
}
OWNERSHIP = {
    "storm-producer-wiring": {
        "owns": ["tests/test_storm_producer.py"],
        "hooks": ["squatch/storm.py", "squatch/box.py", "squatch/daemon.py", "tests/test_storm.py"],
    },
    "storm-notification-activation": {
        "owns": ["tests/test_storm_notification_activation.py"],
        "hooks": ["squatch/storm.py", "squatch/box.py", "squatch/daemon.py", "squatch/__main__.py",
                  "tests/test_storm.py", "tests/test_storm_producer.py", "tests/test_drain.py"],
    },
    "phase3-continue-17": {"owns": ["tickets", "tests/test_seeded_phase3_17.py"], "hooks": []},
}
CONTEXT = {
    "storm-producer-wiring": (
        "squatch/storm.py", "squatch/box.py", "squatch/daemon.py", "tests/test_storm.py",
        "tests/test_box.py", "tests/test_daemon_composition.py",
    ),
    "storm-notification-activation": (
        "squatch/storm.py", "squatch/box.py", "squatch/daemon.py", "squatch/__main__.py",
        "tests/test_storm.py", "tests/test_box.py", "tests/test_daemon_composition.py",
    ),
    "phase3-continue-17": (
        "tests/test_seeded_phase3_11.py", "tests/test_storm.py", "tests/test_box.py",
        "tests/test_daemon_composition.py",
    ),
}
EXISTING_AT_AUTHORING = {
    "tests/test_seeded_phase3_11.py": 9238,
    "squatch/storm.py": 3661,
    "squatch/box.py": 12324,
    "squatch/daemon.py": 15521,
    "squatch/__main__.py": 17521,
    "tests/test_storm.py": 4559,
    "tests/test_box.py": 8419,
    "tests/test_daemon_composition.py": 21280,
}
PLAN_SECTION_AT_AUTHORING = 21923
PRESERVATION = ("tests/test_box.py", "tests/test_daemon_composition.py")
MIGRATION = {
    "storm-producer-wiring": ("tests/test_storm.py",),
    "storm-notification-activation": ("tests/test_storm.py", "tests/test_storm_producer.py",
                                      "tests/test_drain.py"),
}
ACTIVATION_ON_DEMAND = {"tests/test_drain.py"}
NEW_PATH_OWNERS = {
    "tests/test_storm_producer.py": "storm-producer-wiring",
    "tests/test_storm_notification_activation.py": "storm-notification-activation",
    "tests/test_seeded_phase3_17.py": "phase3-continue-17",
    "tests/test_storm_hold.py": "storm-dispatch-hold",
    "tests/test_seeded_phase3_18.py": "phase3-continue-18",
}
SIBLING_NEW = {
    "tests/test_storm_producer.py", "tests/test_storm_notification_activation.py",
    "tests/test_seeded_phase3_17.py",
}
HOLD_OWNERSHIP = {
    "storm-dispatch-hold": {
        "owns": ["tests/test_storm_hold.py"],
        "hooks": ["squatch/storm.py", "squatch/control.py", "squatch/daemon.py",
                  "squatch/drain.py", "squatch/__main__.py", "tests/test_storm.py",
                  "tests/test_storm_producer.py", "tests/test_storm_notification_activation.py"],
    },
    "phase3-continue-18": {"owns": ["tickets", "tests/test_seeded_phase3_18.py"], "hooks": []},
}
HOLD_CONTEXT = (
    "squatch/storm.py", "squatch/control.py", "squatch/daemon.py", "tests/test_storm.py",
    "tests/test_storm_producer.py", "tests/test_storm_notification_activation.py",
    "tests/test_daemon_composition.py",
)
HOLD_ON_DEMAND = {"squatch/drain.py", "squatch/__main__.py"}
FULL = (
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
    assert tuple(BATCH) == ("storm-producer-wiring", "storm-notification-activation",
                            "phase3-continue-17")
    assert len(BATCH) == config.seeding.max_seeds_per_admission == 3
    [contract] = [block["ownership"] for block in _yaml("phase3-continue-16")
                  if isinstance(block, dict)]
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
    assert SIBLING_NEW == {path for path, owner in NEW_PATH_OWNERS.items() if owner in BATCH}
    for path, owner in NEW_PATH_OWNERS.items():
        assert path in (OWNERSHIP | HOLD_OWNERSHIP)[owner]["owns"]


def test_existing_context_has_no_exceptions_or_sibling_new_paths_and_preserves_tests():
    assert set(EXISTING_AT_AUTHORING) == set().union(*map(set, CONTEXT.values()))
    for stem in BATCH:
        ticket = _ticket(stem)
        assert set(ticket.context).isdisjoint(SIBLING_NEW | {"tests/test_seeded_phase3_16.py"})
        assert set(ticket.context).isdisjoint({"squatch/specs.py", "specs/implement.md"})
        for path in ticket.context:
            assert (REPO / path).is_file()
            assert DATA_MARKER not in (REPO / path).read_text()
        for path in ticket.scope_fence:
            if path == "tickets" or path in SIBLING_NEW or path in ACTIVATION_ON_DEMAND:
                continue
            assert path in ticket.context, (stem, path)
    for stem, migration in MIGRATION.items():
        ticket = _ticket(stem)
        assert {"squatch/storm.py", "tests/test_storm.py"} <= set(ticket.context)
        assert set(PRESERVATION) <= set(ticket.context)
        assert set(PRESERVATION).isdisjoint(ticket.scope_fence)
        assert set(migration) <= set(ticket.scope_fence)
        _phrases(stem, "Scope in", [*PRESERVATION, "read-only preservation", "unchanged"])
    activation = _ticket("storm-notification-activation")
    assert "squatch/__main__.py" in activation.scope_fence
    assert ACTIVATION_ON_DEMAND <= set(activation.scope_fence)
    assert ACTIVATION_ON_DEMAND.isdisjoint(activation.context)
    assert "tests/test_storm_producer.py" not in activation.context
    _phrases("storm-notification-activation", "Scope in", [
        "created by the depends-predecessor storm-producer-wiring", "sibling-new at authoring"])


def test_producer_identity_scoped_binding_reconciliation_and_dormancy_contract():
    _phrases("storm-producer-wiring", "Scope in", [
        "optional keyword `occurrence_recorder=`", "default None", "explicit non-None recorder first",
        "`contextvars.ContextVar` in `squatch/box.py`",
        "daemon.compose_daemon_storm_producer(*, state_dir, journal, fs, clock)",
        "synchronous context manager that spawns no tasks",
        "Callers must await every task that inherited the binding before leaving the scope",
        "including exceptional unwind", "checks cover the current context only",
        "Nested scopes restore the previous binding",
        "box.py never imports daemon.py", "Reset the ContextVar token",
        "including on Boxes constructed before scope entry", "unrelated state directories",
        "runner, stages, merge, triage, and author", "without editing those construction modules",
        "Persist the box record first", "`occurrence_id=<box_id>/<reports>`",
        "`signature=message.signature`", "`emitting_stage=message.stage`",
        "signature-dedup hit", "`storm-occurrence/<signature>/<occurrence_id>`",
        "replay appends no second event", "every missing `<box_id>/<n>`", "`1..reports`",
        "regardless of resolution status", "ordered by box seq then n",
        "append-time envelope timestamp from the Journal's injected clock",
        "Already-recorded occurrences keep their timestamps", "a failed box write produces no occurrence",
        "lock-holding engine's composed Box", "`python -m squatch.box ingest` is out of scope",
        "test_production_import_closure_does_not_reach_the_dormant_ledger",
        "production composition remains dormant", "AST call-site reachability",
        "no trip signal, P0 report, notification, or dispatch hold",
    ])
    _phrases("storm-producer-wiring", "Acceptance criteria", [
        "synchronous context manager spawns no tasks",
        "callers await every task that inherited the binding before leaving the scope",
        "including exceptional unwind", "in the current context only",
        "inactive after normal and exceptional scope exit", "1..reports",
        "append-time Journal clock timestamps", "covers resolved records"])
    _phrases("storm-producer-wiring", "Scope out", [
        "unscoped module-global", "permanently installed recorder"])


def test_notification_is_production_replay_safe_and_does_not_own_dispatch_hold():
    _phrases("storm-notification-activation", "Scope in", [
        "`squatch/__main__.py`", "_RestartRunner session wrapper",
        "runner, stages, merge, triage, author", "harvest/second-problem path",
        "verification-attribution failure_report path", "daemon-only construction is not activation",
        "`K=5`", "`T=1 hour`",
        "deterministic over `(signature, first_live_occurrence_id, crossing_occurrence_id)`",
        "`storm-trip/<trip_id>`", "held-state intent is data only", "one P0 `failure_report`",
        "Box records carry no priority field", "`storm-breaker:P0:<trip_id>`",
        "Preserve the Message schema and ordinary enqueue arguments",
        "without incrementing reports", "distinct trips cannot collapse",
        "excluded from occurrence recording, including reconciliation",
        "Unbound ordinary enqueue records nothing", "never a journal writer",
        "each event's original envelope timestamp", "between trip signal and report enqueue",
        "replay cannot mint a second trip", "emitting_stage=None", "no push transport",
        "Dispatch suppression stays exclusively in `storm-dispatch-hold`",
        "real drain work after a trip", "dispatch still proceeds",
        "test_bootstrap_drain_never_scans_or_mutates_the_box",
        "fenced on-demand inspection exception", "neither mutates nor triages",
    ])


def test_continuation_pins_production_hold_ownership_and_future_context_partition():
    stem = "phase3-continue-17"
    [contract] = [block["ownership"] for block in _yaml(stem) if isinstance(block, dict)]
    assert contract == HOLD_OWNERSHIP
    scope = _section(stem, "Scope in")
    embedded = scope.split("The hold's exact embedded Context is ", 1)[1].split(", in that order.", 1)[0]
    assert tuple(re.findall(r"`([^`]+)`", embedded)) == HOLD_CONTEXT
    hooks = set(HOLD_OWNERSHIP["storm-dispatch-hold"]["hooks"])
    assert hooks - set(HOLD_CONTEXT) == HOLD_ON_DEMAND
    assert set(HOLD_CONTEXT) - hooks == {"tests/test_daemon_composition.py"}
    assert {"tests/test_storm_producer.py", "tests/test_storm_notification_activation.py"} <= hooks
    _phrases(stem, "Scope in", [
        "hold depends on phase3-continue-17", "KNOWN-DEEP high/high",
        "phase3-continue-18 depends on storm-dispatch-hold and remains medium/medium",
        "section 20 alone", "75m/150m", "cap 3",
        "drain offer is a whole ticket", "emitting_stage stays diagnostic",
        "emitting_origin", "stem equals the tripped emitting_origin",
        "always present as string or null", "legacy events lacking it as None",
        "optional argument defaulting to None", "Trip and occurrence identities remain unchanged",
        "before durable dispatch accounting including retry-cap draws",
        "Other stems remain eligible", "non-ticket origin creates no global hold",
        "identity-bound resume exactly once", "current-lifecycle control inbox",
        "No later admission activates this hold", "production owner before phase3-exit",
        "Only `squatch/drain.py` and `squatch/__main__.py`",
        "Every other existing fence path is existing Context",
        "three storm tests are the predecessor migration partition",
        "exact occurrence/trip body, key-set, and `_event` fixture assertions",
        "Retain occurrence identity, trip-id, report",
        "merged predecessors when the hold is authored, NOT sibling-new",
        "tests/test_daemon_composition.py` is read-only preservation Context",
        "PRESERVATION set", "both then and pin their measured authoring-time sizes",
        "every max-effort render under REQ_RENDER_HEADROOM", "high-tier hold render",
        "section 20's historical length", "established seeded-test pattern",
        "squatch/git.py and tests/test_git.py",
        "exact Context is squatch/daemon.py, squatch/git.py and tests/test_git.py",
    ])


def test_successor_suffix_removes_only_the_producer_notification_pair():
    assert _admissions("phase3-continue-16") == FULL
    successor = _admissions("phase3-continue-17")
    assert successor == FULL[1:]
    assert successor[0] == ("storm-dispatch-hold",)
    stems = [stem for row in successor for stem in row]
    assert len(stems) == len(set(stems)) and set(FULL[0]).isdisjoint(stems)


def test_authoring_time_sizes_section_length_and_every_max_effort_render():
    # Historical fixtures survive required edits to the production and test hooks.
    assert PLAN_SECTION_AT_AUTHORING == 21923
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
