"""Second Phase 5 admission and its bounded continuation."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import DATA_MARKER, RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket


REPO = Path(__file__).resolve().parent.parent
FEATURES = ("status-projection", "baseline-binding-reader")
CONTINUE = "phase5-continue-03"
ROW = (*FEATURES, CONTINUE)
FULL = (
    ROW,
    ("retro-doctor-cli", "phase5-continue-04"),
    ("phase5-exit",),
)
CONTEXT = {
    "status-projection": (
        "squatch/status.py", "squatch/scorecard.py", "tests/test_scorecard.py",
        "squatch/box.py", "tests/test_box.py",
    ),
    "baseline-binding-reader": ("squatch/config.py", "squatch/policy.py"),
    CONTINUE: ("tests/test_seeded_phase5_01.py",),
}
FENCES = {
    "status-projection": (
        "squatch/status.py", "tests/test_status.py", "squatch/scorecard.py",
        "tests/test_scorecard.py", "squatch/box.py", "tests/test_box.py",
        "squatch/retro.py", "tests/test_retro.py", "squatch/__main__.py",
        "tests/test_cli.py", "tests/test_verbs.py", "tests/test_drain.py",
        "tests/test_drain_upgrade.py", "tests/test_seeded_phase2.py",
    ),
    "baseline-binding-reader": (
        "squatch/baseline.py", "tests/test_baseline.py", "squatch/journal.py",
        "squatch/config.py", "squatch/policy.py", "tests/test_policy.py",
        "squatch/author.py", "tests/test_author.py", "tests/test_retro_box.py",
    ),
    CONTINUE: ("tickets", "tests/test_seeded_phase5_03.py"),
}
# Historical synthetic render fixtures, never live-size assertions.
EXISTING_AT_AUTHORING = {
    "squatch/status.py": 6505,
    "squatch/scorecard.py": 2937,
    "tests/test_scorecard.py": 4912,
    "squatch/box.py": 20244,
    "tests/test_box.py": 8419,
    "squatch/config.py": 10606,
    "squatch/policy.py": 3917,
    "tests/test_seeded_phase5_01.py": 9731,
    "tests/test_seeded_phase4_05.py": 8111,
}
NEW_PATHS = {
    "tests/test_seeded_phase5_02.py", "tests/test_status.py",
    "squatch/baseline.py", "tests/test_baseline.py", "tests/test_seeded_phase5_03.py",
}
SECTION_20_CHARS_AT_AUTHORING = 55841


def _path(stem):
    return REPO / TICKETS_DIR / stem / TICKET_FILE


def _ticket(stem):
    return lint_ticket(
        _path(stem).read_text(), stem=stem, repo=REPO,
        plan=(REPO / "tests/fixtures/squatch_plan_v1.md").read_text(),
        resolve_stem=lambda candidate: _path(candidate).is_file(),
    )


def _section(stem, name):
    lines = _path(stem).read_text().splitlines()
    start = lines.index(f"## {name}") + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")),
               len(lines))
    return "\n".join(lines[start:end])


def _flat(stem, section):
    return " ".join(_section(stem, section).split())


def _admissions(stem):
    [rows] = [yaml.safe_load(block) for block in re.findall(
        r"```yaml\n(.*?)\n```", _section(stem, "Scope in"), re.S)
        if isinstance(yaml.safe_load(block), list)]
    return tuple(tuple(row) for row in rows)


def _context(paths):
    return "".join(
        f"### {path}\n{'x' * EXISTING_AT_AUTHORING[path]}\n" for path in paths
    )


def _authoring_plan():
    current = (REPO / "tests/fixtures/squatch_plan_v1.md").read_text()
    start = current.index("## 20.")
    end = current.index("\n## ", start + 1) + 1
    heading = current[start:current.index("\n", start) + 1]
    section = heading + "x" * (SECTION_20_CHARS_AT_AUTHORING - len(heading) - 1) + "\n"
    return current[:start] + section + current[end:]


def test_second_row_identity_edges_tiers_budgets_fences_and_cap():
    config = load(REPO / "config.yaml", cwd=REPO)
    expected_edges = {
        "status-projection": ("scorecard-reporting", "retro-box-activation"),
        "baseline-binding-reader": ("retro-box-activation",),
        CONTINUE: (*FEATURES,),
    }
    assert _admissions("phase5-continue-02") == FULL
    assert tuple(expected_edges) == ROW
    assert len(ROW) <= config.seeding.max_seeds_per_admission == 3
    for stem, depends in expected_edges.items():
        ticket = _ticket(stem)
        assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
        assert ticket.depends == depends
        assert ticket.plan_sections == ("20",)
        assert (ticket.agent_tier, ticket.agent_effort) == ("medium", "medium")
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
        assert ticket.stuck_minutes <= config.drain.max_ticket_minutes
        assert ticket.scope_fence == FENCES[stem]


def test_context_partition_synthetic_sizes_and_render_headroom():
    assert _ticket("phase5-continue-02").context == ("tests/test_seeded_phase4_05.py",)
    assert (REPO / "tests/test_seeded_phase4_05.py").is_file()
    assert "tests/test_seeded_phase4_05.py" not in NEW_PATHS
    for stem, paths in CONTEXT.items():
        ticket = _ticket(stem)
        assert ticket.context == paths
        assert set(paths) <= set(EXISTING_AT_AUTHORING)
        assert set(paths).isdisjoint(NEW_PATHS | {"tests/test_seeded_phase5_02.py"})
        assert set(paths).isdisjoint({"squatch/specs.py", "specs/implement.md"})
        assert all(DATA_MARKER not in (REPO / path).read_text() for path in paths)
        for path in ticket.scope_fence:
            if path not in {"tickets", "tests/test_status.py", "squatch/baseline.py",
                            "tests/test_baseline.py", "tests/test_seeded_phase5_03.py"}:
                assert path in paths or f"`{path}`" in _section(stem, "Scope in")

    status_scope = _section("status-projection", "Scope in")
    baseline_scope = _section("baseline-binding-reader", "Scope in")
    for text in (
        "squatch/retro.py`\n(17745 bytes)", "tests/test_retro.py` (20072 bytes)",
        "squatch/__main__.py`\n(24624 bytes)", "tests/test_cli.py` (19367 bytes)",
        "tests/test_verbs.py` (9901\nbytes)", "tests/test_drain.py` (42002 bytes)",
        "tests/test_drain_upgrade.py` (14377 bytes)",
    ):
        assert text in status_scope
    for text in (
        "squatch/journal.py`\n(8792 bytes)", "squatch/author.py` (15087 bytes)",
        "tests/test_policy.py` (4836\nbytes)", "tests/test_author.py` (19061 bytes)",
        "tests/test_retro_box.py`\n(29276 bytes)",
    ):
        assert text in baseline_scope

    spec = load_spec(REPO / "specs" / "implement.md")
    limit = int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
    for stem in ROW:
        rendered = spec.render({
            "workspace": DataBlock("engine", f"stem: {stem}\nbranch: {stem}\n"
                                   f"run record: tickets/{stem}/{RUN_RECORD}\n"),
            "ticket": DataBlock("host", _path(stem).read_text()),
            "context": DataBlock("host", _context(CONTEXT[stem])),
        }, plan=_authoring_plan(), plan_sections=("20",), effort="max")
        assert len(rendered) <= limit, (stem, len(rendered), limit)


def test_status_projection_preserves_surface_and_adds_only_closed_projection():
    scope = _flat("status-projection", "Scope in")
    for text in (
        "Preserve every merged `Status` field and existing CLI/file/slash rendering",
        "`unparsed`, `pending`, `in_flight`, `ready`, `blocked`, `stopped`, `merged`, `intake`, `spend_usd`, `calls`, `box`, and `reject_queue`",
        "Add only `box_activity`, `tombstone_digest`, and `scorecard`",
        "sorted stems whose latest terminal transition is `merged`",
        "sorted `(stem, run_seq)` for latest unmatched `running`",
        "sorted `(stem, unmet_dependencies)` for confirmed unmerged tickets with an unmerged declared dependency",
        "Sum numeric `effect_completion.body.cost.usd`", "count Box records by current status",
        "`(box_id, signature, reports, reopened)` for tombstone-resolved records",
        "injected clock", "actual HEAD through `Git.rev_parse`", "real `specs/retro.md` version",
        "`Window(events, clock()).projection(sha=head_sha, spec_version=retro_spec.version)`",
        "before `project_scorecard`", "public CLI exit/output contract",
        "Exclude malformed optional metric bodies", "journal-envelope corruption fail-closed",
        "no journal, Box, ticket, or filesystem write",
    ):
        assert text in scope
    assert "tests/test_cli.py" in _section("status-projection", "Verification")
    assert "tests/test_drain_upgrade.py" in _section("status-projection", "Verification")


def test_baseline_reader_and_remaining_suffix_are_closed_and_terminal():
    baseline = _flat("baseline-binding-reader", "Scope in")
    for text in (
        "BaselineResolution(state, binds)", "`ABSENT | NO_GO | GO | REVOKED`",
        "resolve_baseline(config, events, *, specs_dir)", "latest complete `signal` of kind `review_baseline`",
        "no record is `ABSENT`", "latest non-`GO` verdict is `NO_GO`",
        "every recorded review and author tier identity equals current `Registry(config)` resolution",
        "spec_major` equals the major versions from `specs_dir/review.md` and `specs_dir/author.md`",
        "Otherwise it is `REVOKED`; only `GO` sets `binds=true`",
        "Torn journal tails, malformed identity/spec fields, missing or empty routing, unresolved placeholders, unknown tiers, and unreadable specs never escape",
        "Migrate and remove `policy.go_binds`", "`policy.starting_state` remains sole starting-state policy",
        "`squatch/author.py` is the sole production caller", "`Journal.read()` events, and `<repo>/specs`",
        "`resolution.binds` to `policy.starting_state`",
    ):
        assert text in baseline
    assert "tests/test_policy.py" in _section("baseline-binding-reader", "Verification")
    assert "tests/test_author.py" in _section("baseline-binding-reader", "Verification")
    assert "tests/test_retro_box.py" in _section("baseline-binding-reader", "Verification")

    scope = _flat(CONTINUE, "Scope in")
    assert _admissions(CONTINUE) == FULL[1:]
    for text in (
        "embeds merged `tests/test_seeded_phase5_01.py`, never its own new seeded test",
        "`retro-doctor-cli` starts medium/medium, cites section 20 alone, and owns new `squatch/doctor.py`, new `tests/test_doctor.py`, plus `squatch/retro.py`, `squatch/__main__.py`, `tests/test_retro.py`, `tests/test_cli.py`, and `tests/test_verbs.py`",
        "`retro-doctor-cli` depends on both `status-projection` and `baseline-binding-reader`",
        "The doctor ticket embeds `squatch/retro.py` (17745 bytes) and `tests/test_retro.py` (20072 bytes)",
        "Its measured on-demand exceptions are `squatch/__main__.py` (24624 bytes), `tests/test_cli.py` (19367 bytes), and `tests/test_verbs.py` (9901 bytes)",
        "`phase5-continue-04` depends on `retro-doctor-cli`, owns only `tickets` and new `tests/test_seeded_phase5_04.py`",
        "embeds merged `tests/test_seeded_phase5_02.py`, never its own test nor sibling-new `tests/test_seeded_phase5_03.py`",
        "`phase5-exit` is KNOWN-HARD high/high", "depends transitively on every Phase 5 stem",
        "owns `tickets`, new `tests/test_phase5_exit.py`, and new `tests/test_seeded_phase6_core.py`, and has no successor",
    ):
        assert text in scope
    assert "phase5-continue-05" not in scope


def test_phase5_exit_and_phase6_use_compact_section20_render_surface():
    plan = (REPO / "tests/fixtures/squatch_plan_v1.md").read_text()
    section20 = plan[plan.index("## 20."):]
    for text in (
        "Phase 5/6 compact-render correction",
        "`phase5-exit`, `core-renderer`, `core-drift-classifier`, `phase6-continue`, and every later Phase 6 seed cite section 20 ALONE",
        "full section 19 is never rendered for these tickets",
        "The remaining Phase 6 admissions are fixed here rather than read from section 19",
        "then `phase6-exit` alone with no successor",
        "no historical section-19 snapshot or live section-19 render is accepted",
    ):
        assert text in section20

    spec = load_spec(REPO / "specs" / "implement.md")
    rendered = spec.render({
        "workspace": DataBlock("engine", "stem: phase5-exit\nbranch: phase5-exit\n"),
        "ticket": DataBlock("host", "# compact Phase 5 exit fixture\n"),
        "context": DataBlock("host", ""),
    }, plan=plan, plan_sections=("20",), effort="max")
    assert len(rendered) <= int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)


def test_phase6_remaining_registry_closes_contracts_paths_and_edges():
    plan = (REPO / "tests/fixtures/squatch_plan_v1.md").read_text()
    section20 = plan[plan.index("## 20."):]
    contracts = {
        "core-drift-activation": ("squatch/hostfiles.py", "core-drift-classifier"),
        "migrate-config": ("squatch/config.py", "core-renderer"),
        "host-contract-doc": ("docs/host-contract.md", "migrate-config"),
        "fixture-host-scaffold": ("hosts/fixture/", "host-contract-doc"),
        "bug-gate-grammar": ("tests/test_bug_gate.py", "fixture-host-scaffold"),
        "report-inbox-triage": ("squatch/inbox.py", "bug-gate-grammar"),
        "escape-column": ("squatch/scorecard.py", "report-inbox-triage"),
        "supervised-merge-hold": ("tests/test_supervised_merge_hold.py", "escape-column"),
        "go-grade-machinery": ("tests/test_go_grade.py", "supervised-merge-hold"),
        "go-grade-run": ("tickets/go-grade-run/review-baseline-report.json", "go-grade-machinery"),
        "exit-receipt-machinery": ("eval/host_loop.py", "go-grade-run"),
        "phase6-exit": ("tickets/phase6-exit/exit-receipt.json", "exit-receipt-machinery"),
    }
    for stem, (owned_path, dependency) in contracts.items():
        assert f"`{stem}`" in section20
        assert f"`{owned_path}`" in section20
        assert f"`{dependency}`" in section20
    for tail in range(2, 9):
        assert f"`phase6-continue-{tail:02d}`" in section20
    assert "Phase 6 remaining-row contracts (DECIDED)" in section20
    assert "The exact remaining admission rows and direct edges are therefore" in section20
    assert "alone and terminal" in section20
    assert "`squatch/providers.py`, `squatch/__main__.py`" in section20
    assert "both `_core` and `core_drift` call that function" in section20
    assert "replaces `test_classifier_is_unreachable_from_production_gates`" in section20
    assert "`test_rendering_has_no_git_or_commit_effect` remains" in section20
    assert "The sole supported older schema is version 0" in section20
    assert "changes only that scalar to integer 1 and keeps every other key byte-for-byte" in section20
    assert "A valid current version-1 file is a byte-identical no-op" in section20
    assert "sibling-new `docs/host-contract.md` is excluded at authoring" in section20
    assert "the directory `hosts/fixture/` is a named measured on-demand worktree read" in section20
