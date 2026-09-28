"""Provider cooldown admission and the shrinking Phase 4 suffix."""

from pathlib import Path
import re

import pytest
import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import DATA_MARKER, RENDER_BOUND_CHARS, DataBlock, RenderRefused, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket


REPO = Path(__file__).resolve().parent.parent
BATCH = {
    "provider-cooldown-failover": ("watchdog-activation",),
    "phase4-continue-03": ("provider-cooldown-failover",),
}
OWNERSHIP = {
    "provider-cooldown-failover": {
        "owns": ["tests/test_provider_cooldown_failover.py"],
        "hooks": ["squatch/providers.py", "squatch/timers.py", "squatch/runner.py",
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
CONTEXT = {
    "provider-cooldown-failover": (
        "squatch/providers.py", "squatch/timers.py", "tests/test_providers.py",
        "tests/test_restart_timers.py",
    ),
    "phase4-continue-03": ("tests/test_seeded_phase4_01.py",),
}
ON_DEMAND = {
    "squatch/runner.py", "squatch/restart.py", "squatch/daemon.py", "squatch/stages.py",
    "squatch/merge.py", "squatch/drain.py", "squatch/serve.py", "squatch/__main__.py",
    "eval/shakeout/bench.py", "eval/daemon_soak.py", "tests/test_serve.py",
    "tests/test_merge.py", "tests/test_mergequeue.py", "tests/test_daemon_composition.py",
    "tests/test_stages.py",
}
EXISTING_AT_AUTHORING = {
    "squatch/providers.py": 18687, "squatch/timers.py": 4912,
    "tests/test_providers.py": 32667, "tests/test_restart_timers.py": 11675,
    "tests/test_seeded_phase4_01.py": 12352,
}
ON_DEMAND_AT_AUTHORING = {
    "squatch/runner.py": 23428, "squatch/restart.py": 909, "squatch/daemon.py": 20691,
    "squatch/stages.py": 55886, "squatch/merge.py": 29250, "squatch/drain.py": 26170,
    "squatch/serve.py": 11768, "squatch/__main__.py": 20298,
    "eval/shakeout/bench.py": 8372, "eval/daemon_soak.py": 25471,
    "tests/test_serve.py": 16160, "tests/test_merge.py": 33179,
    "tests/test_mergequeue.py": 46142, "tests/test_daemon_composition.py": 21267,
    "tests/test_stages.py": 50162,
}
# Measured from section 20 through its final newline at adafe69.
SECTION_20_CHARS_AT_AUTHORING = 34153
NEW_PATH_OWNERS = {
    "tests/test_provider_cooldown_failover.py": "provider-cooldown-failover",
    "tests/test_seeded_phase4_03.py": "phase4-continue-03",
    "tests/test_reliability_battery.py": "reliability-battery",
    "tests/test_seeded_phase4_04.py": "phase4-continue-04",
    "tests/test_seeded_phase4_05.py": "phase4-continue-05",
}
PREDECESSOR = {
    "tests/test_watchdog.py": "kwargs-passthrough",
    "tests/test_kill_cli_activation.py": "kwargs-passthrough",
    "tests/test_storm_notification_activation.py": "kwargs-passthrough",
    "tests/test_seeded_phase3_06.py": "ticket-text-only",
}
FULL = (
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


def _context(paths, sizes):
    return "".join(f"### {path}\n{'x' * sizes[path]}\n" for path in paths)


def _authoring_plan():
    current = (REPO / PLAN_FILE).read_text()
    start = current.index("## 20.")
    end = current.index("\n## ", start + 1) + 1
    heading = current[start:current.index("\n", start) + 1]
    section = heading + "x" * (SECTION_20_CHARS_AT_AUTHORING - len(heading) - 1) + "\n"
    return current[:start] + section + current[end:]


def test_exact_seeds_edges_tiers_budgets_and_ownership_fences():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert tuple(BATCH) == FULL[0]
    assert len(BATCH) <= config.seeding.max_seeds_per_admission == 3
    [ownership] = [block["ownership"] for block in _yaml("phase4-continue-02")
                   if isinstance(block, dict) and "ownership" in block]
    assert ownership == OWNERSHIP
    for stem, depends in BATCH.items():
        ticket = _ticket(stem)
        tier = ("high", "high") if stem == "provider-cooldown-failover" else ("medium", "medium")
        assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
        assert ticket.depends == depends and ticket.plan_sections == ("20",)
        assert (ticket.agent_tier, ticket.agent_effort) == tier
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
        assert ticket.stuck_minutes <= config.drain.max_ticket_minutes
        assert ticket.scope_fence == tuple(OWNERSHIP[stem]["owns"] + OWNERSHIP[stem]["hooks"])


def test_context_closure_delimiters_new_paths_and_predecessor_closure():
    for stem in BATCH:
        ticket = _ticket(stem)
        assert ticket.context == CONTEXT[stem]
        assert set(ticket.context) <= set(EXISTING_AT_AUTHORING)
        assert set(ticket.context).isdisjoint(NEW_PATH_OWNERS)
        assert set(ticket.context).isdisjoint({"squatch/specs.py", "specs/implement.md"})
        for path in ticket.context:
            assert DATA_MARKER not in (REPO / path).read_text()
        for path in ticket.scope_fence:
            if path in NEW_PATH_OWNERS:
                assert NEW_PATH_OWNERS[path] == stem
            elif path == "tickets":
                continue
            elif path in ON_DEMAND:
                assert stem == "provider-cooldown-failover"
            else:
                assert path in ticket.context, (stem, path)
    provider = _ticket("provider-cooldown-failover")
    assert ON_DEMAND.isdisjoint(provider.context)
    assert ON_DEMAND <= set(provider.scope_fence)
    assert all((REPO / path).is_file() for path in ON_DEMAND)
    for path, classification in PREDECESSOR.items():
        content = (REPO / path).read_text()
        if classification == "kwargs-passthrough":
            assert "original(**kwargs)" in content
        else:
            assert "def compose_pipeline" in content and "Scope in" in content
    callers = set()
    pattern = re.compile(r"(?:stages\.compose|compose_pipeline|compose_daemon_timers|"
                         r"restart_session|Serve\(|Session\()")
    for root in (REPO / "tests", REPO / "eval"):
        for path in root.rglob("*.py"):
            if pattern.search(path.read_text()):
                callers.add(path.relative_to(REPO).as_posix())
    callers.discard(Path(__file__).relative_to(REPO).as_posix())
    assert callers <= set(provider.scope_fence) | set(PREDECESSOR)


def test_authoring_sizes_and_measured_on_demand_headroom():
    spec = load_spec(REPO / "specs" / "implement.md")
    plan = _authoring_plan()
    limit = int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
    provider = _ticket("provider-cooldown-failover")
    workspace = ("stem: provider-cooldown-failover\nbranch: provider-cooldown-failover\n"
                 f"run record: tickets/provider-cooldown-failover/{RUN_RECORD}\n")
    context = _context(provider.context, EXISTING_AT_AUTHORING)
    rendered = spec.render({"workspace": DataBlock("engine", workspace),
                            "ticket": DataBlock("host", _path(provider.stem).read_text()),
                            "context": DataBlock("host", context)}, plan=plan,
                           plan_sections=provider.plan_sections, effort="max")
    assert len(rendered) <= limit, (len(rendered), limit)
    inspected = _context(provider.context + tuple(sorted(ON_DEMAND)),
                         EXISTING_AT_AUTHORING | ON_DEMAND_AT_AUTHORING)
    with pytest.raises(RenderRefused, match="over the 160000-char bound"):
        spec.render({"workspace": DataBlock("engine", workspace),
                     "ticket": DataBlock("host", _path(provider.stem).read_text()),
                     "context": DataBlock("host", inspected)}, plan=plan,
                    plan_sections=provider.plan_sections, effort="max")
    for stem in BATCH:
        ticket = _ticket(stem)
        rendered = spec.render({
            "workspace": DataBlock("engine", f"stem: {stem}\nbranch: {stem}\n"
                                   f"run record: tickets/{stem}/{RUN_RECORD}\n"),
            "ticket": DataBlock("host", _path(stem).read_text()),
            "context": DataBlock("host", _context(ticket.context, EXISTING_AT_AUTHORING)),
        }, plan=plan, plan_sections=ticket.plan_sections, effort="max")
        assert len(rendered) <= limit, (stem, len(rendered), limit)


def test_complete_suffix_sequence_and_successor_removes_only_first_row():
    assert _admissions("phase4-continue-02") == FULL
    successor = _admissions("phase4-continue-03")
    assert successor == FULL[1:]
    assert successor[0] == ("reliability-battery", "phase4-continue-04")
    assert all(len(row) <= 3 for row in FULL)
    stems = [stem for row in FULL for stem in row]
    assert len(stems) == len(set(stems))
    assert [row[-1] for row in FULL[:-1]] == [
        "phase4-continue-03", "phase4-continue-04", "phase4-continue-05",
    ]
    assert FULL[-1] == ("phase4-exit",)
    assert "phase4-continue-06" not in stems
