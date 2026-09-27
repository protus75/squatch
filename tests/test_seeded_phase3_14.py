"""Flake identity contracts and the shrinking Phase 3 continuation."""

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
    "flake-detection": ("phase3-continue-14",),
    "flake-release": ("flake-detection",),
    "phase3-continue-15": ("flake-detection", "flake-release"),
}
OWNERSHIP = {
    "flake-detection": {
        "owns": ["squatch/flake.py", "tests/test_flake.py"],
        "hooks": ["squatch/daemon.py"],
    },
    "flake-release": {
        "owns": [],
        "hooks": ["squatch/flake.py", "tests/test_flake.py", "squatch/daemon.py"],
    },
    "phase3-continue-15": {
        "owns": ["tickets", "tests/test_seeded_phase3_15.py"], "hooks": [],
    },
}
CONTEXT = {
    "flake-detection": (
        "squatch/journal.py", "squatch/timers.py", "squatch/daemon.py",
        "squatch/box.py", "squatch/config.py",
    ),
    "flake-release": (
        "squatch/journal.py", "squatch/box.py", "squatch/daemon.py", "squatch/merge.py",
    ),
    "phase3-continue-15": (
        "tests/test_seeded_phase3_11.py", "squatch/journal.py", "tests/test_journal.py",
    ),
}
# Historical fixtures, not live-size invariants: the seeded work owns these paths.
EXISTING_AT_AUTHORING = {
    "tests/test_seeded_phase3_11.py": 9238,
    "squatch/journal.py": 7110,
    "squatch/timers.py": 4912,
    "squatch/daemon.py": 15279,
    "squatch/box.py": 12324,
    "squatch/config.py": 10260,
    "tests/test_journal.py": 9535,
    "squatch/merge.py": 23865,
}
PLAN_SECTION_AT_AUTHORING = 17942
NEW_PATH_OWNERS = {
    "squatch/restart.py": "restart-timers",
    "squatch/timers.py": "restart-timers",
    "tests/test_restart_timers.py": "restart-timers",
    "squatch/flake.py": "flake-detection",
    "tests/test_flake.py": "flake-detection",
    "tests/test_seeded_phase3_14.py": "phase3-continue-14",
    "tests/test_seeded_phase3_15.py": "phase3-continue-15",
}
PRESERVATION = ("tests/test_journal.py",)
FULL = (
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
    return lint_ticket(
        _path(stem).read_text(), stem=stem, repo=REPO,
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


def test_exact_seeds_edges_tiers_budgets_cap_fences_and_new_path_owners():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert tuple(BATCH) == ("flake-detection", "flake-release", "phase3-continue-15")
    assert len(BATCH) == config.seeding.max_seeds_per_admission == 3
    [contract] = [block["ownership"] for block in _yaml("phase3-continue-14")
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

    from test_seeded_phase3_13 import NEW_PATH_OWNERS as predecessor_owners
    assert NEW_PATH_OWNERS == predecessor_owners
    for path, owner in NEW_PATH_OWNERS.items():
        assert path in _ticket(owner).scope_fence


def test_context_partition_has_no_sibling_new_paths_or_inspection_exceptions():
    sibling_new = {path for path, owner in NEW_PATH_OWNERS.items() if owner in BATCH}
    assert set(EXISTING_AT_AUTHORING) == set().union(*map(set, CONTEXT.values()))
    for stem in BATCH:
        ticket = _ticket(stem)
        assert ticket.context == CONTEXT[stem]
        assert set(ticket.context).isdisjoint(sibling_new)
        assert set(ticket.context).isdisjoint({"squatch/specs.py", "specs/implement.md"})
        for path in ticket.context:
            assert (REPO / path).is_file()
            assert "<<<squatch:" not in (REPO / path).read_text()
        for path in ticket.scope_fence:
            if path == "tickets":
                continue
            if path in sibling_new:
                owner = NEW_PATH_OWNERS[path]
                assert owner == stem or (stem == "flake-release" and owner == "flake-detection")
            else:
                assert path in ticket.context, (stem, path)
    assert "squatch/merge.py" not in _ticket("flake-release").scope_fence
    for stem in ("flake-detection", "flake-release"):
        assert "tests/test_daemon_composition.py" not in _ticket(stem).scope_fence
        assert "on-demand Context exception" in _section(stem, "Definition of rejected")


def test_detection_pins_rerun_identity_quarantine_fold_and_deferred_cap_policy():
    scope = _section("flake-detection", "Scope in")
    criteria = _section("flake-detection", "Acceptance criteria")
    for phrase in (
        "A check that fails then passes on a bare re-run (same workspace, no code change)",
        "is a bug signal, not a pass", "signature-deduped report `signature`",
        "Suggestion Box `box_id`", "test quarantine ledger",
        "exactly the named `test_id` entry keyed by `box_id`", "changing no other entry",
    ):
        assert phrase in scope
    for text in (scope, criteria):
        for phrase in ("`signal`", "`flake/<box_id>`",
                       "{kind: flake_detected, test_id, signature, box_id}",
                       "detection writes no release record or release state"):
            assert phrase in text
    assert "survives reconstruction" in criteria
    assert "deduplicates the same report" in criteria
    scope_out = _section("flake-detection", "Scope out")
    for phrase in ("`caps.quarantine` bound", "cap-crossing halt", "escalation path"):
        assert phrase in scope_out


def test_release_pins_separate_sources_ordering_no_release_cases_and_idempotence():
    scope = _section("flake-release", "Scope in")
    criteria = _section("flake-release", "Acceptance criteria")
    for phrase in (
        "SAME ledger entry", "`flake/<box_id>`",
        "{kind: flake_detected, test_id, signature, box_id}",
        "`Box.get(box_id).status == \"authored\"`",
        "`Box.get(box_id).resolution.link == fix_stem` exactly",
        "journal `state_transition` to `merged` for that exact `fix_stem`",
        "read through `squatch.journal`", "separate typed explicit input",
        "`squatch/merge.py` is the emitter", "`ticket=fix_stem`",
        '`body.to == "merged"`', "`run_seq`, `commit`, and `reviewed_sha`",
        "merged `author-stage` path in `squatch/author.py`",
        '`status="authored", link=authored.stem`',
        "production supply belongs to a later activation",
        "Manual `resume` remains the separate operator override",
    ):
        assert phrase in scope
    for text in (scope, criteria):
        for phrase in ("`signal`", "`flake-release/<box_id>/<fix_stem>`",
                       "{kind: flake_released, test_id, signature, box_id, fix_stem}",
                       "BEFORE folding the entry out of quarantine",
                       "A second release of the same identity appends no event and changes no state"):
            assert phrase in text
    for phrase in ("wrong box status", "link mismatch", "unmerged stem",
                   "missing or red rerun", "append-before-removal reconstruction"):
        assert phrase in criteria


def test_boundaries_pin_call_path_dormancy_and_reject_sha_state():
    for stem in ("flake-detection", "flake-release"):
        scope = _section(stem, "Scope in")
        criteria = _section(stem, "Acceptance criteria")
        assert "`compose_daemon_flake`-style" in scope
        assert "direct proof lives in fenced `tests/test_flake.py`" in scope
        assert "read-only preservation evidence, with no requested migration" in scope
        for text in (scope, criteria):
            assert ("No production composition in `squatch/__main__.py` or "
                    "`squatch/drain.py` calls or constructs the hook") in text
            assert "through `squatch/daemon.py` is allowed" in text
        assert "never a SHA-held set" in scope
        assert "No SHA-held set substitutes" in criteria
        verify = _section(stem, "Verification")
        assert "uv run pytest tests/test_flake.py -q" in verify
        assert "uv run pytest tests/test_daemon_composition.py -q" in verify


def test_successor_edges_ownership_context_and_predecessor_preservation():
    [ownership] = [block["ownership"] for block in _yaml("phase3-continue-15")
                   if isinstance(block, dict) and "ownership" in block]
    assert ownership == {
        "journal-roll": {
            "owns": ["tests/test_journal_roll.py"], "hooks": ["squatch/journal.py"],
        },
        "storm-ledger": {
            "owns": ["squatch/storm.py", "tests/test_storm.py"], "hooks": [],
        },
        "phase3-continue-16": {
            "owns": ["tickets", "tests/test_seeded_phase3_16.py"], "hooks": [],
        },
    }
    continuation = _ticket("phase3-continue-15")
    assert set(PRESERVATION) <= set(continuation.context)
    assert set(PRESERVATION).isdisjoint(continuation.scope_fence)
    for section in ("Scope in", "Acceptance criteria"):
        text = _section("phase3-continue-15", section)
        for phrase in ("journal-roll", "storm-ledger", "`tests/test_journal.py`",
                       "read-only preservation for both journal-roll and storm-ledger",
                       "`PRESERVATION` set", "every existing fence path is existing Context",
                       "authoring-time Context sizes", "max-effort render",
                       "`REQ_RENDER_HEADROOM`"):
            assert phrase in text
    scope = _section("phase3-continue-15", "Scope in")
    assert "`journal-roll` depends on `phase3-continue-15`" in scope
    assert "`storm-ledger` depends on `journal-roll`" in scope
    assert "`phase3-continue-16` depends on both" in scope
    assert "`squatch/storm.py`" not in _section("phase3-continue-15", "Context")


def test_successor_removes_only_flake_pair_without_combining_admissions():
    assert _admissions("phase3-continue-14") == FULL
    successor = _admissions("phase3-continue-15")
    assert successor == FULL[1:]
    assert successor[0] == ("journal-roll", "storm-ledger")
    stems = [stem for row in successor for stem in row]
    assert len(stems) == len(set(stems))
    assert set(FULL[0]).isdisjoint(stems)


def test_authoring_sizes_section_length_and_max_effort_headroom():
    assert PLAN_SECTION_AT_AUTHORING == 17942
    spec = load_spec(REPO / "specs" / "implement.md")
    plan = (REPO / PLAN_FILE).read_text()
    section = plan.split("## 20. Open decisions", 1)[1].split("## 21.", 1)[0]
    limit = int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
    for stem in BATCH:
        ticket = _ticket(stem)
        context = "".join(f"### {path}\n{'x' * EXISTING_AT_AUTHORING[path]}\n"
                          for path in ticket.context)
        workspace = f"stem: {stem}\nbranch: {stem}\nrun record: tickets/{stem}/{RUN_RECORD}\n"
        rendered = spec.render({
            "workspace": DataBlock("engine", workspace),
            "ticket": DataBlock("host", _path(stem).read_text()),
            "context": DataBlock("host", context),
        }, plan=plan, plan_sections=ticket.plan_sections, effort="max")
        historical_length = len(rendered) - max(0, len(section) - PLAN_SECTION_AT_AUTHORING)
        assert historical_length <= limit, (stem, historical_length, limit)
