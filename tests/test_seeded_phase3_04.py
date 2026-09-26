"""Dispatch construction seeds and the next finite Phase 3 admission."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket

REPO = Path(__file__).resolve().parent.parent
PHASE3_04 = {
    "dispatch-admission-boundary": ("phase3-continue-04",),
    "dispatch-config-snapshot": ("dispatch-admission-boundary",),
    "phase3-continue-05": ("dispatch-config-snapshot",),
}
FENCES = {
    "dispatch-admission-boundary": ("squatch/daemon.py", "tests/test_daemon_admission.py"),
    "dispatch-config-snapshot": (
        "squatch/daemon.py", "squatch/config.py", "tests/test_daemon_admission.py",
        "tests/test_daemon_config.py",
    ),
    "phase3-continue-05": ("tickets", "tests/test_seeded_phase3_05.py"),
}
OWNERSHIP = {
    "dispatch-admission-boundary": {
        "owns": ["squatch/daemon.py", "tests/test_daemon_admission.py"], "hooks": [],
    },
    "dispatch-config-snapshot": {
        "owns": ["tests/test_daemon_config.py"],
        "hooks": ["squatch/daemon.py", "squatch/config.py", "tests/test_daemon_admission.py"],
    },
}
CONTEXT = {
    "dispatch-admission-boundary": (),
    "dispatch-config-snapshot": ("squatch/config.py",),
    "phase3-continue-05": (
        "tickets/phase3-continue-04/ticket.md", "tests/test_seeded_phase3_core.py",
        "squatch/scheduler.py", "squatch/watcher.py", "squatch/__main__.py",
        "tests/test_scheduler.py",
    ),
}

# Verified against main at 45d2307a73d24d3ca54c5f8e3ef885e4d0b6d21a.
# Sizes are synthetic render inputs only; future live content is not an invariant.
EXISTING_AT_AUTHORING = {
    "squatch/config.py": 10110,
    "tickets/phase3-continue-04/ticket.md": 4954,
    "tests/test_seeded_phase3_core.py": 5877,
    "squatch/scheduler.py": 1899,
    "squatch/watcher.py": 537,
    "squatch/__main__.py": 10340,
    "tests/test_scheduler.py": 4261,
}
# All dispatch fence paths, classified from main rather than this worktree.
NEW_AT_AUTHORING = {
    "squatch/daemon.py", "tests/test_daemon_admission.py", "tests/test_daemon_config.py",
    "tests/test_seeded_phase3_05.py",
}
SUFFIX = (
    ("scheduler-activation",),
    ("merge-queue-activation", "rework-activation"),
    ("background-consumers", "control-inbox"),
    ("dispatch-pause-boundary", "pause-resume-activation"),
    ("kill-signal-journal", "kill-executor-abort"),
    ("kill-worker-stop", "kill-failure-suppression"),
    ("kill-cli-activation",),
    ("heartbeat",),
    ("restart-timers",),
    ("flake-detection", "flake-release"),
    ("journal-roll", "storm-ledger"),
    ("storm-producer-wiring", "storm-notification-activation"),
    ("storm-dispatch-hold",),
    ("checkpoint-push",),
    ("daemon-soak",),
    ("soak-run",),
    ("phase3-exit",),
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


def _yaml_blocks(stem):
    return [yaml.safe_load(block) for block in re.findall(
        r"```yaml\n(.*?)\n```", _section(stem, "Scope in"), re.S)]


def test_emitted_batch_is_exact_linted_and_capped():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert tuple(PHASE3_04) == (
        "dispatch-admission-boundary", "dispatch-config-snapshot", "phase3-continue-05")
    assert set(re.findall(r"`tickets/([^/]+)/ticket\.md`",
                          _section("phase3-continue-04", "Scope in"))) == set(PHASE3_04)
    assert len(PHASE3_04) <= config.seeding.max_seeds_per_admission
    for stem, depends in PHASE3_04.items():
        ticket = _ticket(stem)
        assert (ticket.source, ticket.state) == ("seed", "confirmed"), stem
        assert ticket.plan_sections == ("20",), stem
        assert ticket.depends == depends, stem
        assert (ticket.agent_tier, ticket.agent_effort) == ("medium", "medium"), stem
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150), stem
        assert 0 < ticket.expected_minutes < ticket.stuck_minutes <= config.drain.max_ticket_minutes


def test_fences_main_context_closure_and_keyed_registry_ownership():
    for stem, fence in FENCES.items():
        ticket = _ticket(stem)
        assert ticket.scope_fence == fence, stem
        assert ticket.context == CONTEXT[stem], stem
        assert set(ticket.context) <= set(EXISTING_AT_AUTHORING), stem
        for entry in fence:
            if entry == "tickets":
                continue  # The registry's authoring directory, not a Context file.
            assert entry in EXISTING_AT_AUTHORING or entry in NEW_AT_AUTHORING
            if entry in EXISTING_AT_AUTHORING:
                assert entry in ticket.context, (stem, entry)
    for stem, record in OWNERSHIP.items():
        assert _yaml_blocks(stem) == [{"ownership": {stem: record}}]
        assert set(record["owns"] + record["hooks"]) == set(FENCES[stem])
    assert set(EXISTING_AT_AUTHORING).isdisjoint(NEW_AT_AUTHORING)
    assert "tests/test_seeded_phase3_04.py" not in EXISTING_AT_AUTHORING


def test_dispatch_predecessor_test_closure():
    # Admission only creates files. Snapshot may migrate that predecessor's
    # callback arguments, so its test travels inside the successor's fence.
    admission = "dispatch-admission-boundary"
    snapshot = "dispatch-config-snapshot"
    assert set(FENCES[admission]) <= NEW_AT_AUTHORING
    assert "tests/test_daemon_admission.py" in _ticket(snapshot).scope_fence
    assert set(FENCES[snapshot]) - NEW_AT_AUTHORING == {"squatch/config.py"}
    # The only existing production hook is additive: pin the authoring contract
    # that preserves config tests and the scheduler's production-root negative.
    assert "Do not change Config fields, defaults, load/parse signatures or validation behavior" in _section(snapshot, "Scope out")
    for stem in (admission, snapshot):
        assert "Preserve the existing production import closure" in _path(stem).read_text()
        assert "tests/test_scheduler.py" in _section(stem, "Verification")
    assert "tests/test_config.py" in _section(snapshot, "Verification")
    assert "not absence of production imports or CLI verbs" in _section(admission, "Acceptance criteria")
    assert "New tests contain no global dormancy/CLI-absence assertion" in _section(snapshot, "Scope out")


def test_successor_ownership_and_predecessor_closure_contract():
    successor = "phase3-continue-05"
    assert _yaml_blocks(successor)[0] == {"ownership": {
        "scheduler-activation": {
            "owns": ["tests/test_daemon_composition.py"],
            "hooks": ["squatch/daemon.py", "squatch/scheduler.py", "squatch/watcher.py",
                      "squatch/__main__.py", "tests/test_scheduler.py"],
        },
        "phase3-continue-06": {
            "owns": ["tickets", "tests/test_seeded_phase3_06.py"], "hooks": [],
        },
    }}
    criteria = _section(successor, "Acceptance criteria")
    assert "proves predecessor-test closure" in criteria
    assert "unless that test is also fenced" in criteria
    for path in ("tests/test_scheduler.py", "tests/test_daemon_admission.py",
                 "tests/test_daemon_config.py"):
        assert path in criteria
    assert "predecessor-test closure requires a path outside the registry fence" in _section(successor, "Definition of rejected")


def test_successor_pins_context_existence_as_well_as_render_sizes():
    # A live existence check turns green seed proofs red when owner files land.
    criteria = _section("phase3-continue-05", "Acceptance criteria")
    closure = next(line for line in criteria.splitlines()
                   if "pins an `EXISTING_AT_AUTHORING` map" in line)
    assert "set(context) <= EXISTING_AT_AUTHORING" in closure
    assert "every fence entry in that map to appear in that seed's Context" in closure
    assert "Never check live existence on main" in closure
    assert "Use this same map as the source of synthetic render sizes" in closure
    assert "remain outside this pinned map after later merges" in closure
    for path in ("squatch/daemon.py", "tests/test_daemon_admission.py",
                 "tests/test_daemon_config.py", "tests/test_daemon_composition.py"):
        assert path in closure


def test_continuation_carries_the_exact_ordered_suffix():
    blocks = _yaml_blocks("phase3-continue-05")
    assert len(blocks) == 3
    assert tuple(tuple(group) for group in blocks[1]) == SUFFIX
    assert tuple(tuple(group) for group in blocks[2]) == SUFFIX[1:]
    parent = _yaml_blocks("phase3-continue-04")
    assert tuple(tuple(group) for group in parent[0]) == (
        ("dispatch-admission-boundary", "dispatch-config-snapshot"), *SUFFIX)
    assert tuple(tuple(group) for group in parent[1]) == SUFFIX


def test_every_seed_render_fits_requisition_headroom_with_pinned_context():
    spec = load_spec(REPO / "specs" / "implement.md")
    plan = (REPO / PLAN_FILE).read_text()
    limit = int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
    for stem in PHASE3_04:
        ticket = _ticket(stem)
        workspace = f"stem: {stem}\nbranch: {stem}\nrun record: {TICKETS_DIR}/{stem}/{RUN_RECORD}\n"
        context = "".join(f"### {path}\n{'x' * EXISTING_AT_AUTHORING[path]}\n"
                          for path in ticket.context)
        rendered = spec.render({
            "workspace": DataBlock("engine", workspace),
            "ticket": DataBlock("host", _path(stem).read_text()),
            "context": DataBlock("host", context or "(no Context files)\n"),
        }, plan=plan, plan_sections=ticket.plan_sections, effort="max")
        assert len(rendered) <= limit, (stem, len(rendered), limit)
