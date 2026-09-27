"""Phase 4 core seed and finite-continuation contracts."""

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
    "watchdog-event-stream": ("phase3-exit",),
    "notify-transport": ("phase3-exit",),
    "phase4-continue": ("watchdog-event-stream", "notify-transport"),
}
OWNERSHIP = {
    "watchdog-event-stream": (
        "squatch/watchdog.py", "squatch/providers.py", "squatch/seams.py",
        "tests/test_watchdog.py", "tests/test_providers.py", "tests/test_seams.py",
    ),
    "notify-transport": (
        "squatch/notify.py", "squatch/config.py", "squatch/seams.py",
        "squatch/serve.py", "squatch/__main__.py", "tests/test_notify.py",
        "tests/test_config.py", "tests/test_seams.py", "tests/test_serve.py",
    ),
    "phase4-continue": ("tickets", "tests/test_seeded_phase4_01.py"),
}
CONTEXT = {
    "watchdog-event-stream": (
        "squatch/providers.py", "squatch/seams.py", "tests/test_providers.py",
        "tests/test_seams.py",
    ),
    "notify-transport": (
        "squatch/config.py", "squatch/seams.py", "squatch/serve.py",
        "tests/test_serve.py",
    ),
    "phase4-continue": ("tests/test_seeded_phase3_11.py",),
}
ON_DEMAND = {
    "watchdog-event-stream": (),
    "notify-transport": (
        "squatch/__main__.py", "tests/test_config.py", "tests/test_seams.py",
    ),
    "phase4-continue": (),
}
EXISTING_AT_AUTHORING = {
    "squatch/providers.py": 16650,
    "squatch/seams.py": 6942,
    "tests/test_providers.py": 28569,
    "tests/test_seams.py": 7000,
    "squatch/config.py": 10260,
    "squatch/serve.py": 10680,
    "tests/test_serve.py": 9235,
    "tests/test_seeded_phase3_11.py": 9238,
}
NEW_PATH_OWNERS = {
    "squatch/watchdog.py": "watchdog-event-stream",
    "tests/test_watchdog.py": "watchdog-event-stream",
    "squatch/notify.py": "notify-transport",
    "tests/test_notify.py": "notify-transport",
    "tests/test_seeded_phase4_01.py": "phase4-continue",
}
ADMISSIONS = (
    ("watchdog-detector", "watchdog-activation", "phase4-continue-02"),
    ("provider-cooldown-failover", "phase4-continue-03"),
    ("reliability-battery", "phase4-continue-04"),
    ("reliability-run", "phase4-continue-05"),
    ("phase4-exit",),
)
PAYLOADS = (
    "watchdog-detector", "watchdog-activation", "provider-cooldown-failover",
    "reliability-battery", "reliability-run", "phase4-exit",
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


def _admissions():
    [block] = [yaml.safe_load(raw) for raw in re.findall(
        r"```yaml\n(.*?)\n```", _section("phase4-continue", "Scope in"), re.S)]
    return tuple(tuple(row) for row in block)


def test_exact_core_batch_edges_tiers_budgets_cap_and_fences():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert tuple(BATCH) == (
        "watchdog-event-stream", "notify-transport", "phase4-continue")
    assert len(BATCH) <= config.seeding.max_seeds_per_admission == 3

    for stem, depends in BATCH.items():
        ticket = _ticket(stem)
        assert (ticket.source, ticket.state, ticket.priority) == (
            "seed", "confirmed", "P1")
        assert ticket.depends == depends
        assert ticket.plan_sections == ("20",)
        assert (ticket.agent_tier, ticket.agent_effort) == ("medium", "medium")
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
        assert ticket.stuck_minutes <= config.drain.max_ticket_minutes
        assert ticket.scope_fence == OWNERSHIP[stem]


def test_closed_ownership_context_new_paths_and_on_demand_partition():
    observed_new = {}
    for stem in BATCH:
        ticket = _ticket(stem)
        assert ticket.context == CONTEXT[stem]
        assert set(ticket.context) <= set(EXISTING_AT_AUTHORING)
        assert set(ticket.context).isdisjoint(
            set(NEW_PATH_OWNERS) | {"squatch/specs.py", "specs/implement.md"})
        for path in ticket.context:
            assert DATA_MARKER not in (REPO / path).read_text()
        for path in ticket.scope_fence:
            if path in NEW_PATH_OWNERS:
                observed_new[path] = stem
            elif path == "tickets":
                continue
            elif path in ON_DEMAND[stem]:
                assert path not in ticket.context
            else:
                assert path in ticket.context, (stem, path)

    assert observed_new == NEW_PATH_OWNERS
    assert not ON_DEMAND["watchdog-event-stream"]
    assert set(ON_DEMAND["notify-transport"]) == {
        "squatch/__main__.py", "tests/test_config.py", "tests/test_seams.py"}
    notify_scope = _section("notify-transport", "Scope in")
    for path in ON_DEMAND["notify-transport"]:
        assert f"`{path}`" in notify_scope
    for phrase in (
        "private `SubprocessExec`", "`Notifications.notify(argv)`",
        "startup before\ndispatch and again on every watcher poll",
        "keyword whose default means no transport", "status-only behavior",
        "real `_serve` passes a non-default wrapper",
    ):
        assert phrase in notify_scope

    watchdog_scope = _section("watchdog-event-stream", "Scope in")
    for phrase in (
        "in-flight event callback", "spool capture",
        "production construction supplies no callback",
        "only when a consumer was supplied", "final unterminated line",
        "existing fake or wrapper with the current signature",
    ):
        assert phrase in watchdog_scope


def test_repaired_callback_and_notification_preservation_criteria():
    watchdog_criteria = _section("watchdog-event-stream", "Acceptance criteria")
    for phrase in (
        "in order and exactly once", "final unterminated line",
        "no-consumer call's exact kwargs", "normalized adapter events",
    ):
        assert phrase in watchdog_criteria

    notify_criteria = _section("notify-transport", "Acceptance criteria")
    for phrase in (
        "default notification keyword", "status-only behavior",
        "real `_serve` passes a non-default wrapper",
        "tests/test_daemon_soak_runner.py",
    ):
        assert phrase in notify_criteria


def test_finite_ordered_suffix_continuations_and_terminal_batch():
    admissions = _admissions()
    assert admissions == ADMISSIONS
    assert all(1 <= len(row) <= 3 for row in admissions)
    assert admissions[-1] == ("phase4-exit",)
    continuations = tuple(item for row in admissions for item in row
                          if item.startswith("phase4-continue-"))
    assert continuations == tuple(f"phase4-continue-{n:02d}" for n in range(2, 6))
    payloads = tuple(item for row in admissions for item in row
                     if not item.startswith("phase4-continue-"))
    assert payloads == PAYLOADS
    assert len(payloads) == len(set(payloads))
    assert admissions[1][0] == "provider-cooldown-failover"
    assert len(admissions[1]) == 2

    continuation = _ticket("phase4-continue")
    assert continuation.depends == ("watchdog-event-stream", "notify-transport")
    scope = _section("phase4-continue", "Scope in")
    assert "`watchdog-detector` depends on both" in scope
    assert "`watchdog-activation` depends on `watchdog-detector`" in scope
    assert "next continuation depends on `watchdog-activation`" in scope
    assert "terminal admission contains only `phase4-exit`" in scope


def test_ticket_structure_and_authoring_time_max_effort_render_headroom():
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

        verification = _section(stem, "Verification")
        assert "uv run pytest" in verification
        assert "uv run pytest -q" in verification
