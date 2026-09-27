"""First kill-boundary seeds and their shrinking Phase 3 successor."""

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
    "kill-signal-journal": ("phase3-continue-09",),
    "kill-executor-abort": ("kill-signal-journal",),
    "phase3-continue-10": ("kill-signal-journal", "kill-executor-abort"),
}
CONTEXT = {
    "kill-signal-journal": ("squatch/control.py", "squatch/daemon.py"),
    "kill-executor-abort": ("squatch/daemon.py", "squatch/driver.py"),
    "phase3-continue-10": ("tests/test_seeded_phase3_core.py",),
}
OWNERSHIP = {
    "kill-signal-journal": {"owns": ["tests/test_kill_signal_journal.py"],
                            "hooks": ["squatch/control.py", "squatch/daemon.py"]},
    "kill-executor-abort": {"owns": ["tests/test_kill_executor_abort.py"],
                            "hooks": ["squatch/daemon.py", "squatch/driver.py"]},
    "phase3-continue-10": {"owns": ["tickets", "tests/test_seeded_phase3_10.py"],
                            "hooks": []},
}
EXISTING_AT_AUTHORING = {
    "tests/test_seeded_phase3_core.py": 5877,
    "squatch/control.py": 10215,
    "squatch/daemon.py": 8749,
    "squatch/driver.py": 9738,
}
NEW_PATH_OWNERS = {
    "tests/test_kill_signal_journal.py": "kill-signal-journal",
    "tests/test_kill_executor_abort.py": "kill-executor-abort",
    "tests/test_seeded_phase3_10.py": "phase3-continue-10",
}
FULL = (
    ("kill-signal-journal", "kill-executor-abort"),
    ("kill-worker-stop", "kill-failure-suppression"), ("kill-cli-activation",),
    ("heartbeat",), ("restart-timers",), ("flake-detection", "flake-release"),
    ("journal-roll", "storm-ledger"),
    ("storm-producer-wiring", "storm-notification-activation"),
    ("storm-dispatch-hold",), ("checkpoint-push",), ("daemon-soak",),
    ("soak-run",), ("phase3-exit",))
SUCCESSOR = FULL[1:]


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


def test_exact_kill_seeds_edges_budgets_cap_fences_and_contexts():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert tuple(BATCH) == ("kill-signal-journal", "kill-executor-abort", "phase3-continue-10")
    assert len(BATCH) == config.seeding.max_seeds_per_admission == 3
    for stem, depends in BATCH.items():
        ticket = _ticket(stem)
        assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
        assert ticket.depends == depends and ticket.plan_sections == ("20",)
        assert (ticket.agent_tier, ticket.agent_effort) == ("medium", "medium")
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
        assert ticket.stuck_minutes <= config.drain.max_ticket_minutes == 180
        assert ticket.context == CONTEXT[stem]
        assert ticket.scope_fence == tuple(OWNERSHIP[stem]["owns"] + OWNERSHIP[stem]["hooks"])


def test_kill_ownership_context_closure_and_cli_exclusion():
    assert set(EXISTING_AT_AUTHORING).isdisjoint(NEW_PATH_OWNERS)
    assert NEW_PATH_OWNERS == {
        "tests/test_kill_signal_journal.py": "kill-signal-journal",
        "tests/test_kill_executor_abort.py": "kill-executor-abort",
        "tests/test_seeded_phase3_10.py": "phase3-continue-10",
    }
    for stem in BATCH:
        ticket = _ticket(stem)
        assert set(ticket.context) <= set(EXISTING_AT_AUTHORING)
        assert set(ticket.context).isdisjoint({"squatch/specs.py", "specs/implement.md"})
        for path in ticket.scope_fence:
            if path in EXISTING_AT_AUTHORING:
                assert path in ticket.context, (stem, path)
            elif path != "tickets":
                assert NEW_PATH_OWNERS[path] == stem
        assert "squatch/__main__.py" not in ticket.context
        assert "squatch/__main__.py" not in ticket.scope_fence
    for stem in ("kill-signal-journal", "kill-executor-abort"):
        [record] = [block["ownership"] for block in _yaml(stem)
                    if isinstance(block, dict) and "ownership" in block]
        assert record == {stem: OWNERSHIP[stem]}


def test_kill_boundaries_pin_their_independent_predecessor_contracts():
    signal = _section("kill-signal-journal", "Scope in")
    executor = _section("kill-executor-abort", "Scope in")
    assert "journals its accepted or stale decision before any cancellation mutation" in signal
    assert "current lifecycle identity" in signal and "kill CLI verb" in signal
    assert "active `Driver` invocation" in executor
    assert "preserving `asyncio.CancelledError` propagation" in executor
    assert "worker-stop" in executor and "failure suppression" in executor
    assert "tests/test_kill_signal_journal.py" in _section("kill-executor-abort", "Verification")


def test_successor_suffix_is_exact_and_synthetic_renders_fit_headroom():
    assert SUCCESSOR == FULL[1:]
    [admissions] = [block for block in _yaml("phase3-continue-10") if isinstance(block, list)]
    assert tuple(tuple(row) for row in admissions) == SUCCESSOR
    scope = _section("phase3-continue-10", "Scope in")
    for phrase in ("configured seeding cap 3", "exact identities, edges, tiers, budgets",
                   "new-path owners", "max-effort render headroom", "successor suffix equality",
                   "established seeded-test pattern", "Sibling-new paths"):
        assert phrase in scope
    spec = load_spec(REPO / "specs" / "implement.md")
    plan = (REPO / PLAN_FILE).read_text()
    for stem in BATCH:
        ticket = _ticket(stem)
        context = "".join(f"### {path}\n{'x' * EXISTING_AT_AUTHORING[path]}\n"
                          for path in ticket.context)
        workspace = f"stem: {stem}\nbranch: {stem}\nrun record: tickets/{stem}/{RUN_RECORD}\n"
        rendered = spec.render({"workspace": DataBlock("engine", workspace),
                                "ticket": DataBlock("host", _path(stem).read_text()),
                                "context": DataBlock("host", context)}, plan=plan,
                               plan_sections=ticket.plan_sections, effort="max")
        assert len(rendered) <= RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM
