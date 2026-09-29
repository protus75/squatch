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
        plan=(REPO / PLAN_FILE).read_text(),
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
    current = (REPO / PLAN_FILE).read_text()
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
