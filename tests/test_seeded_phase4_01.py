"""First bounded Phase 4 admission and its immutable continuation suffix."""

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
    "watchdog-detector": ("watchdog-event-stream", "notify-transport"),
    "watchdog-activation": ("watchdog-detector",),
    "phase4-continue-02": ("watchdog-activation",),
}
OWNERSHIP = {
    "watchdog-detector": {
        "owns": ["squatch/watchdog.py", "tests/test_watchdog.py"], "hooks": [],
    },
    "watchdog-activation": {
        "owns": ["tests/test_watchdog_activation.py"],
        "hooks": [
            "squatch/watchdog.py", "squatch/notify.py", "squatch/serve.py",
            "squatch/stages.py", "squatch/drain.py", "squatch/__main__.py",
            "squatch/merge.py", "squatch/providers.py", "tests/test_watchdog.py",
            "tests/test_providers.py", "tests/test_notify.py", "tests/test_serve.py",
            "tests/test_merge.py", "tests/test_mergequeue.py",
        ],
    },
    "phase4-continue-02": {
        "owns": ["tickets", "tests/test_seeded_phase4_02.py"], "hooks": [],
    },
}
CONTEXT = {
    "watchdog-detector": (
        "squatch/watchdog.py", "squatch/providers.py", "tests/test_watchdog.py",
        "tests/test_providers.py",
    ),
    "watchdog-activation": (
        "squatch/watchdog.py", "squatch/notify.py", "squatch/serve.py",
        "tests/test_watchdog.py", "tests/test_notify.py", "tests/test_serve.py",
    ),
    "phase4-continue-02": ("tests/test_seeded_phase3_11.py",),
}
ON_DEMAND = {
    "watchdog-activation": {
        "squatch/stages.py", "squatch/drain.py", "squatch/__main__.py",
        "squatch/merge.py", "squatch/providers.py", "tests/test_providers.py",
        "tests/test_merge.py", "tests/test_mergequeue.py",
    },
}
MIGRATION_FENCE = {
    "phase4-continue-02": [
        "tests/test_seeded_phase4_01.py", "tests/test_seeded_phase3_01.py",
        "tests/test_seeded_phase3_08.py", "tests/test_seeded_phase3_10.py",
    ],
}
EXISTING_AT_AUTHORING = {
    "squatch/watchdog.py": 1008,
    "squatch/providers.py": 18687,
    "tests/test_watchdog.py": 1018,
    "tests/test_providers.py": 32667,
    "squatch/notify.py": 3800,
    "squatch/serve.py": 11768,
    "tests/test_notify.py": 9200,
    "tests/test_serve.py": 16160,
    "tests/test_seeded_phase3_11.py": 9238,
}
NEW_PATH_OWNERS = {
    "tests/test_watchdog_activation.py": "watchdog-activation",
    "tests/test_seeded_phase4_02.py": "phase4-continue-02",
    "tests/test_provider_cooldown_failover.py": "provider-cooldown-failover",
    "tests/test_seeded_phase4_03.py": "phase4-continue-03",
    "tests/test_reliability_battery.py": "reliability-battery",
    "tests/test_seeded_phase4_04.py": "phase4-continue-04",
    "tests/test_seeded_phase4_05.py": "phase4-continue-05",
}
CREATED_IN_THIS_ADMISSION = {
    "tests/test_seeded_phase4_01.py",
    "tickets/watchdog-detector/ticket.md",
    "tickets/watchdog-activation/ticket.md",
    "tickets/phase4-continue-02/ticket.md",
}
FULL = (
    ("watchdog-detector", "watchdog-activation", "phase4-continue-02"),
    ("provider-cooldown-failover", "phase4-continue-03"),
    ("reliability-battery", "phase4-continue-04"),
    ("reliability-run", "phase4-continue-05"),
    ("phase4-exit",),
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


def test_exact_seeds_edges_tiers_budgets_fences_and_owners():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert tuple(BATCH) == FULL[0]
    assert len(BATCH) <= config.seeding.max_seeds_per_admission == 3
    for stem, depends in BATCH.items():
        ticket = _ticket(stem)
        assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
        assert ticket.depends == depends and ticket.plan_sections == ("20",)
        assert (ticket.agent_tier, ticket.agent_effort) == ("medium", "medium")
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
        assert ticket.stuck_minutes <= config.drain.max_ticket_minutes
        assert ticket.scope_fence == tuple(
            OWNERSHIP[stem]["owns"] + OWNERSHIP[stem]["hooks"] + MIGRATION_FENCE.get(stem, []))
    assert NEW_PATH_OWNERS["tests/test_watchdog_activation.py"] == "watchdog-activation"
    assert NEW_PATH_OWNERS["tests/test_seeded_phase4_02.py"] == "phase4-continue-02"


def test_context_closure_delimiters_and_new_path_ownership():
    sibling_new = set(NEW_PATH_OWNERS)
    mutable_paths = {path for ownership in OWNERSHIP.values()
                     for path in ownership["owns"] + ownership["hooks"]}
    for stem in BATCH:
        ticket = _ticket(stem)
        assert ticket.context == CONTEXT[stem]
        assert set(ticket.context) <= set(EXISTING_AT_AUTHORING)
        assert set(ticket.context).isdisjoint(sibling_new)
        assert set(ticket.context).isdisjoint(CREATED_IN_THIS_ADMISSION)
        # Sibling-owned Context was scanned at authoring; later detector and
        # activation edits must not turn this historical admission proof red.
        for path in set(ticket.context) - mutable_paths:
            content = (REPO / path).read_text()
            assert "squatch:data" not in content and "squatch:end" not in content
        for path in ticket.scope_fence:
            if path in NEW_PATH_OWNERS:
                assert NEW_PATH_OWNERS[path] == stem
            elif (path != "tickets" and path not in ON_DEMAND.get(stem, set())
                  and path not in MIGRATION_FENCE.get(stem, [])):
                assert path in ticket.context, (stem, path)
    assert "squatch/specs.py" not in set().union(*map(set, CONTEXT.values()))
    activation = _ticket("watchdog-activation")
    assert ON_DEMAND["watchdog-activation"].isdisjoint(activation.context)
    assert ON_DEMAND["watchdog-activation"] <= set(activation.scope_fence)


def test_requisition_lint_without_files_created_by_this_admission(tmp_path):
    # Requisition needs existing paths, not future sibling implementation bytes.
    # Synthetic base files keep this proof independent of those later edits.
    for path in EXISTING_AT_AUTHORING:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x" * EXISTING_AT_AUTHORING[path])
    assert all(not (tmp_path / path).exists() for path in CREATED_IN_THIS_ADMISSION)
    for stem in BATCH:
        ticket = lint_ticket(
            _path(stem).read_text(), stem=stem, repo=tmp_path,
            plan=(REPO / PLAN_FILE).read_text(),
            resolve_stem=lambda candidate: candidate in BATCH or _path(candidate).is_file())
        assert ticket.context == CONTEXT[stem]


def test_detector_order_and_predecessor_dormancy_migration():
    detector = _section("watchdog-detector", "Scope in")
    for phrase in (
        "All accounting is USD", "WatchdogEvent.usd", "tokens-only event stream",
        "flat USD estimate", "provider-cap wait intervals", "expected * 1.5 >= stuck",
    ):
        assert phrase in detector
    activation = _section("watchdog-activation", "Scope in")
    for phrase in (
        "watchdog-owned LLM wrapper", "Stages.run", "LLMEffect._call",
        "Driver.__init__", "LLMRequest", "kind: watchdog",
        "ticket + spiral + run_seq", "after every dispatch",
        "test_unrelated_signals_and_hold_release_do_not_notify",
        "unrecognized watchdog-kind body", "test_watchdog_construction_has_no_production_callback_consumer",
    ):
        assert phrase in activation
    assert list(BATCH).index("watchdog-detector") < list(BATCH).index("watchdog-activation")


def test_successor_provider_ownership_and_authoring_contract():
    [ownership] = [block["ownership"] for block in _yaml("phase4-continue-02")
                   if isinstance(block, dict) and "ownership" in block]
    assert ownership == {
        "provider-cooldown-failover": {
            "owns": ["tests/test_provider_cooldown_failover.py"],
            "hooks": ["squatch/providers.py", "squatch/watchdog.py", "squatch/timers.py", "squatch/runner.py",
                      "squatch/restart.py", "squatch/daemon.py", "squatch/stages.py",
                      "squatch/merge.py", "tests/test_providers.py",
                      "tests/test_restart_timers.py", "tests/test_stages.py",
                      "squatch/drain.py", "squatch/serve.py", "squatch/__main__.py",
                      "eval/shakeout/bench.py", "eval/daemon_soak.py", "tests/test_serve.py",
                      "tests/test_merge.py", "tests/test_mergequeue.py",
                      "tests/test_daemon_composition.py"],
        },
        "phase4-continue-03": {
            "owns": ["tickets", "tests/test_seeded_phase4_03.py"], "hooks": [],
        },
    }
    for stem, paths in ownership.items():
        for path in paths["owns"]:
            if path != "tickets":
                assert NEW_PATH_OWNERS[path] == stem
        assert all((REPO / path).is_file() for path in paths["hooks"])
    criteria = _section("phase4-continue-02", "Acceptance criteria")
    for phrase in ("high/high provider tier", "medium/medium continuation tier",
                   "predecessor-test closure", "authoring-time Context sizes",
                   "max-effort render", "REQ_RENDER_HEADROOM"):
        assert phrase in criteria
    scope_out = _section("phase4-continue-02", "Scope out")
    assert "Do not implement provider cooldown/failover behavior" in scope_out
    assert "do not author the provider payload now" not in scope_out


def test_complete_finite_suffix_and_successor_removes_only_first_row():
    assert _admissions("phase4-continue") == FULL
    successor = _admissions("phase4-continue-02")
    assert successor == FULL[1:]
    assert successor[0] == ("provider-cooldown-failover", "phase4-continue-03")
    assert all(len(row) <= 3 for row in FULL)
    stems = [stem for row in FULL for stem in row]
    assert len(stems) == len(set(stems))
    assert FULL[-1] == ("phase4-exit",)
    assert [row[-1] for row in FULL[:-1]] == [
        "phase4-continue-02", "phase4-continue-03", "phase4-continue-04",
        "phase4-continue-05",
    ]
    assert "phase4-continue-06" not in stems
    assert not set(FULL[0]) & {stem for row in successor for stem in row}


def test_authoring_sizes_and_max_effort_headroom():
    # Permanent historical render fixtures: sibling tickets must edit these
    # files, so never compare the authoring-time sizes with later live sizes.
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
