"""First Phase 5 admission and its fixed finite suffix."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import DATA_MARKER, RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket


REPO = Path(__file__).resolve().parent.parent
FIRST = "scorecard-reporting"
CONTINUE = "phase5-continue-02"
BATCH = {FIRST: ("retro-box-activation",), CONTINUE: (FIRST,)}
FULL = (
    (FIRST, CONTINUE),
    ("status-projection", "baseline-binding-reader", "phase5-continue-03"),
    ("retro-doctor-cli", "phase5-continue-04"),
    ("phase5-exit",),
)
CONTEXT = {
    FIRST: ("squatch/retro.py", "tests/test_retro.py"),
    CONTINUE: ("tests/test_seeded_phase4_05.py",),
}
FENCES = {
    FIRST: ("squatch/scorecard.py", "tests/test_scorecard.py", "squatch/retro.py", "tests/test_retro.py"),
    CONTINUE: ("tickets", "tests/test_seeded_phase5_02.py"),
}
# Historical synthetic render fixtures, never live-size assertions.
EXISTING_AT_AUTHORING = {
    "squatch/retro.py": 16091,
    "tests/test_retro.py": 20072,
    "tests/test_seeded_phase4_05.py": 8111,
}
SIBLING_NEW = {"squatch/scorecard.py", "tests/test_scorecard.py", "tests/test_seeded_phase5_02.py"}
SECTION_20_CHARS_AT_AUTHORING = 55841


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


def _admissions(stem):
    [rows] = [yaml.safe_load(block) for block in re.findall(
        r"```yaml\n(.*?)\n```", _section(stem, "Scope in"), re.S)
        if isinstance(yaml.safe_load(block), list)]
    return tuple(tuple(row) for row in rows)


def _context(paths):
    return "".join(f"### {path}\n{'x' * EXISTING_AT_AUTHORING[path]}\n" for path in paths)


def _authoring_plan():
    current = (REPO / PLAN_FILE).read_text()
    start = current.index("## 20.")
    end = current.index("\n## ", start + 1) + 1
    heading = current[start:current.index("\n", start) + 1]
    section = heading + "x" * (SECTION_20_CHARS_AT_AUTHORING - len(heading) - 1) + "\n"
    return current[:start] + section + current[end:]


def _flat(stem, section):
    return " ".join(_section(stem, section).split())


def test_first_row_identities_edges_tiers_budgets_fences_and_cap():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert tuple(BATCH) == FULL[0]
    assert len(BATCH) <= config.seeding.max_seeds_per_admission == 3
    for stem, depends in BATCH.items():
        ticket = _ticket(stem)
        assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
        assert ticket.depends == depends
        assert ticket.plan_sections == ("20",)
        assert (ticket.agent_tier, ticket.agent_effort) == ("medium", "medium")
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
        assert ticket.stuck_minutes <= config.drain.max_ticket_minutes
        assert ticket.scope_fence == FENCES[stem]


def test_context_partition_synthetic_fixtures_and_render_headroom():
    assert EXISTING_AT_AUTHORING == {
        "squatch/retro.py": 16091, "tests/test_retro.py": 20072,
        "tests/test_seeded_phase4_05.py": 8111,
    }
    for stem, paths in CONTEXT.items():
        ticket = _ticket(stem)
        assert ticket.context == paths
        assert set(paths) <= set(EXISTING_AT_AUTHORING)
        assert set(paths).isdisjoint(SIBLING_NEW | {"tests/test_seeded_phase5_01.py"})
        assert set(paths).isdisjoint({"squatch/specs.py", "specs/implement.md"})
        assert all(DATA_MARKER not in (REPO / path).read_text() for path in paths)

    spec = load_spec(REPO / "specs" / "implement.md")
    limit = int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
    for stem in BATCH:
        rendered = spec.render({
            "workspace": DataBlock("engine", f"stem: {stem}\nbranch: {stem}\nrun record: tickets/{stem}/{RUN_RECORD}\n"),
            "ticket": DataBlock("host", _path(stem).read_text()),
            "context": DataBlock("host", _context(CONTEXT[stem])),
        }, plan=_authoring_plan(), plan_sections=("20",), effort="max")
        assert len(rendered) <= limit, (stem, len(rendered), limit)


def test_scorecard_contract_is_closed_concrete_and_retro_is_preservation_only():
    scope = _flat(FIRST, "Scope in")
    for text in (
        "(ticket, code, verdict, bypassed)",
        "SurfaceScorecardRow(surface, evaluated_tickets, catches, escapes, bypass_count, catch_rate, escape_rate, prune_candidate)",
        "Scorecard(boundary, merged_ticket_count, spend_usd, tokens, signal_counts, gate_failure_count, surfaces)",
        "project_scorecard(RetroWindow) -> Scorecard",
        "Malformed completions contribute no observation",
        "number of distinct observed tickets for that code",
        "non-bypassed `verdict: fail` observations",
        "catches divided by all observations for that code, zero when absent",
        "Phase 5 has no bug-report producer, so `escapes` and `escape_rate` are exactly zero",
        "evaluated_tickets >= 25",
        "Sort rows by surface",
        "no filesystem, journal, Git, Box, or provider operation",
        "deterministic `## Surface scorecard` table",
        "malformed-input exclusion",
        "input immutability",
        "byte-for-byte unchanged",
    ):
        assert text in scope
    criteria = _flat(FIRST, "Acceptance criteria")
    assert "malformed-input exclusion for completed check invoices" in criteria
    assert "tests/test_retro.py" in _section(FIRST, "Verification")


def test_continuation_pins_its_partition_later_owners_and_terminal_suffix():
    assert _admissions("phase5-continue") == FULL
    assert _admissions(CONTINUE) == FULL[1:]
    scope = _flat(CONTINUE, "Scope in")
    for text in (
        "already- merged `tests/test_seeded_phase4_05.py` continuation pattern",
        "already-merged `tests/test_seeded_phase5_01.py` is the Context pattern for the authored `phase5-continue-03`",
        "new-in-this-admission `tests/test_seeded_phase5_02.py` is excluded from every authored ticket's Context",
        "Sibling-new paths for this admission are `tests/test_status.py`, `squatch/baseline.py`, `tests/test_baseline.py`, and `tests/test_seeded_phase5_03.py`",
        "Merged `squatch/scorecard.py` and `tests/test_scorecard.py` are existing Context for `status-projection`",
        "synthetic fixtures or individually named measured on-demand exceptions",
        "Every existing fence path of these authored seeds is embedded Context or an individually named measured on-demand exception",
        "depends directly on `scorecard-reporting` and `retro-box-activation`",
        "`baseline-binding-reader` depends directly on `retro-box-activation`",
        "preserves all merged `Status` fields and CLI rendering while adding only `box_activity`, `tombstone_digest`, and `scorecard`",
        "sorted set of stems whose latest terminal transition is `merged`",
        "sorted `(stem, run_seq)` for latest unmatched `running` transitions",
        "sums numeric `effect_completion.body.cost.usd`",
        "current-window `project_scorecard` result",
        "resolves actual HEAD through `Git.rev_parse`",
        "`squatch/status.py`, new `tests/test_status.py`, merged `squatch/scorecard.py`, `tests/test_scorecard.py`, `squatch/box.py`, `tests/test_box.py`, `squatch/retro.py`, `tests/test_retro.py`, `squatch/__main__.py`, `tests/test_cli.py`, `tests/test_verbs.py`, `tests/test_drain.py`, and `tests/test_drain_upgrade.py`",
        "`squatch/journal.py`, `squatch/config.py`, `squatch/policy.py`, `tests/test_policy.py`, `squatch/author.py`, `tests/test_author.py`, and `tests/test_retro_box.py`",
        "ABSENT | NO_GO | GO | REVOKED",
        "resolve_baseline(config, events, *, specs_dir)",
        "missing or empty routing, unresolved placeholders, unknown tiers, and unreadable specs resolve to the supervised side without raising",
        "No review-baseline record resolves `ABSENT`",
        "latest verdict other than `GO` resolves `NO_GO`",
        "only `GO` sets `binds=true`",
        "torn tail or malformed identity/spec input is `REVOKED`",
        "`squatch/author.py` is the sole production caller",
        "migrates and removes existing `policy.go_binds`",
        "`phase5-continue-03` depends on both feature stems",
        "`phase5-continue-04` depends on `retro-doctor-cli`",
        "`phase5-exit` is KNOWN-HARD high/high",
        "new `squatch/doctor.py` and `tests/test_doctor.py`, plus `squatch/retro.py`, `squatch/__main__.py`, `tests/test_retro.py`, `tests/test_cli.py`, and `tests/test_verbs.py`",
        "embeds merged `tests/test_seeded_phase5_02.py`, never the seeded test created in its own admission",
        "owns only `tickets` and new `tests/test_seeded_phase5_04.py`",
        "new `tests/test_phase5_exit.py`, and new `tests/test_seeded_phase6_core.py`, and has no successor",
    ):
        assert text in scope
    assert "max-effort `specs/implement.md` render" in scope
    assert "RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM" in scope
    assert "phase5-continue-05" not in scope
    assert all(len(row) <= 3 for row in FULL)
