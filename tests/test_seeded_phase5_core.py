"""Phase 5 core admission and its fixed finite continuation contracts."""

from pathlib import Path
import re

import yaml

from squatch.config import load
from squatch.requisition import REQ_RENDER_HEADROOM
from squatch.specs import DATA_MARKER, RENDER_BOUND_CHARS, DataBlock, load_spec
from squatch.stages import RUN_RECORD
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, lint_ticket


REPO = Path(__file__).resolve().parent.parent
CORE = {
    "retro-drain-invoker": ("phase4-exit",),
    "retro-box-activation": ("retro-drain-invoker",),
    "phase5-continue": ("retro-box-activation",),
}
OWNERSHIP = {
    "retro-drain-invoker": (
        "squatch/retro.py", "specs/retro.md", "tests/test_retro.py",
        "squatch/drain.py", "squatch/driver.py", "squatch/__main__.py",
        "squatch/box.py", "tests/test_drain.py", "tests/test_driver.py",
        "tests/test_box.py", "tests/test_drain_reentry.py",
        "tests/test_drain_upgrade.py",
        "tests/test_daemon_composition.py", "tests/test_kill_cli_activation.py",
        "tests/test_storm_hold.py", "tests/test_storm_notification_activation.py",
        "tests/test_restart_timers.py", "tests/test_provider_cooldown_failover.py",
        "tests/test_watchdog_activation.py", "tests/test_daemon_pause.py",
        "tests/test_control_cli.py",
    ),
    "retro-box-activation": (
        "squatch/retro.py", "squatch/box.py", "squatch/merge.py",
        "squatch/author.py", "squatch/triage.py", "squatch/policy.py",
        "squatch/stages.py", "squatch/runner.py", "squatch/daemon.py",
        "squatch/drain.py", "squatch/serve.py", "squatch/status.py",
        "squatch/__main__.py", "tests/test_box.py", "tests/test_merge.py",
        "tests/test_author.py", "tests/test_triage.py", "tests/test_policy.py",
        "tests/test_stages.py", "tests/test_daemon_composition.py",
        "tests/test_drain.py", "tests/test_serve.py", "tests/test_retro_box.py",
    ),
    "phase5-continue": ("tickets", "tests/test_seeded_phase5_01.py"),
}
CONTEXT = {
    "retro-drain-invoker": (
        "squatch/driver.py", "squatch/git.py", "squatch/box.py",
        "tests/test_seeded_phase4_02.py",
    ),
    "retro-box-activation": (
        "squatch/box.py", "tests/test_box.py", "squatch/author.py",
        "tests/test_seeded_phase4_02.py",
    ),
    "phase5-continue": ("tests/test_seeded_phase4_05.py",),
}
INVOKER_ON_DEMAND = (
    "squatch/drain.py", "squatch/__main__.py", "tests/test_drain.py",
    "tests/test_driver.py", "tests/test_box.py", "tests/test_drain_reentry.py",
    "tests/test_drain_upgrade.py",
    "tests/test_daemon_composition.py", "tests/test_kill_cli_activation.py",
    "tests/test_storm_hold.py", "tests/test_storm_notification_activation.py",
    "tests/test_restart_timers.py", "tests/test_provider_cooldown_failover.py",
    "tests/test_watchdog_activation.py", "tests/test_daemon_pause.py",
    "tests/test_control_cli.py",
)
ACTIVATION_ON_DEMAND = (
    "squatch/merge.py", "squatch/triage.py", "squatch/policy.py",
    "squatch/stages.py", "squatch/runner.py", "squatch/daemon.py",
    "squatch/drain.py", "squatch/serve.py", "squatch/status.py",
    "squatch/__main__.py", "tests/test_merge.py", "tests/test_author.py",
    "tests/test_triage.py", "tests/test_policy.py", "tests/test_stages.py",
    "tests/test_daemon_composition.py", "tests/test_drain.py", "tests/test_serve.py",
)
REGRESSION_SUITES = (
    "tests/test_drain_reentry.py", "tests/test_drain_upgrade.py",
    "tests/test_daemon_composition.py",
    "tests/test_kill_cli_activation.py", "tests/test_storm_hold.py",
    "tests/test_storm_notification_activation.py", "tests/test_restart_timers.py",
    "tests/test_provider_cooldown_failover.py", "tests/test_watchdog_activation.py",
    "tests/test_daemon_pause.py", "tests/test_control_cli.py",
)
EXISTING_AT_AUTHORING = {
    "squatch/driver.py": 10753,
    "squatch/git.py": 7990,
    "squatch/box.py": 15003,
    "tests/test_seeded_phase4_02.py": 10580,
    "tests/test_box.py": 8419,
    "squatch/author.py": 14189,
    "tests/test_seeded_phase4_05.py": 8111,
}
# Measured from section 20 through its final newline at this admission.
SECTION_20_CHARS_AT_AUTHORING = 48486
NEW_PATH_OWNERS = {
    "squatch/retro.py": "retro-drain-invoker",
    "specs/retro.md": "retro-drain-invoker",
    "tests/test_retro.py": "retro-drain-invoker",
    "tests/test_retro_box.py": "retro-box-activation",
    "tests/test_seeded_phase5_01.py": "phase5-continue",
}
SUFFIX = (
    ("scorecard-reporting", "phase5-continue-02"),
    ("status-projection", "baseline-binding-reader", "phase5-continue-03"),
    ("retro-doctor-cli", "phase5-continue-04"),
    ("phase5-exit",),
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
    end = next((index for index in range(start, len(lines))
                if lines[index].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


def _admissions(stem):
    [rows] = [yaml.safe_load(block) for block in re.findall(
        r"```yaml\n(.*?)\n```", _section(stem, "Scope in"), re.S)
        if isinstance(yaml.safe_load(block), list)]
    return tuple(tuple(row) for row in rows)


def _on_demand_exceptions(stem):
    scope = _section(stem, "Scope in")
    match = re.search(
        r"The fenced measured on-demand inspection exceptions are (.*?)\.\n\n",
        scope,
        re.S,
    )
    assert match is not None
    return match.group(1)


def _context(paths):
    return "".join(
        f"### {path}\n{'x' * EXISTING_AT_AUTHORING[path]}\n" for path in paths)


def _authoring_plan():
    current = (REPO / PLAN_FILE).read_text()
    start = current.index("## 20.")
    end = current.index("\n## ", start + 1) + 1
    heading = current[start:current.index("\n", start) + 1]
    section = heading + "x" * (SECTION_20_CHARS_AT_AUTHORING - len(heading) - 1) + "\n"
    return current[:start] + section + current[end:]


def test_exact_core_edges_tiers_budgets_complete_fences_and_admission():
    config = load(REPO / "config.yaml", cwd=REPO)
    assert tuple(CORE) == (
        "retro-drain-invoker", "retro-box-activation", "phase5-continue")
    assert len(CORE) <= config.seeding.max_seeds_per_admission == 3
    assert _admissions("phase4-exit") == (tuple(CORE),)
    for stem, depends in CORE.items():
        ticket = _ticket(stem)
        tier = ("high", "high") if stem.startswith("retro-") else ("medium", "medium")
        assert (ticket.source, ticket.state, ticket.priority) == ("seed", "confirmed", "P1")
        assert ticket.depends == depends and ticket.plan_sections == ("20",)
        assert (ticket.agent_tier, ticket.agent_effort) == tier
        assert (ticket.expected_minutes, ticket.stuck_minutes) == (75, 150)
        assert ticket.stuck_minutes <= config.drain.max_ticket_minutes
        assert ticket.scope_fence == OWNERSHIP[stem]


def test_context_partitions_new_paths_and_measured_exceptions_are_closed():
    on_demand = {
        "retro-drain-invoker": set(INVOKER_ON_DEMAND),
        "retro-box-activation": set(ACTIVATION_ON_DEMAND),
        "phase5-continue": set(),
    }
    for stem in CORE:
        ticket = _ticket(stem)
        assert ticket.context == CONTEXT[stem]
        assert set(ticket.context) <= set(EXISTING_AT_AUTHORING)
        assert set(ticket.context).isdisjoint(NEW_PATH_OWNERS)
        assert set(ticket.context).isdisjoint({"squatch/specs.py", "specs/implement.md"})
        for path in ticket.context:
            assert DATA_MARKER not in (REPO / path).read_text()
        exceptions = _on_demand_exceptions(stem) if on_demand[stem] else ""
        for path in on_demand[stem]:
            assert path in ticket.scope_fence and path not in ticket.context
            assert (REPO / path).is_file()
            assert f"`{path}`" in exceptions
        for path in ticket.scope_fence:
            if path in NEW_PATH_OWNERS:
                assert (NEW_PATH_OWNERS[path] == stem
                        or (stem == "retro-box-activation" and path == "squatch/retro.py"))
            elif path == "tickets" or path == "squatch/retro.py":
                continue
            elif path not in on_demand[stem]:
                assert path in ticket.context, (stem, path)

    activation = _ticket("retro-box-activation")
    assert "squatch/retro.py" not in activation.context
    assert "tests/test_retro.py" not in activation.context
    assert "tests/test_status.py" not in activation.scope_fence
    assert "tests/test_status.py" not in activation.context


def test_authoring_time_sizes_and_max_effort_render_headroom():
    spec = load_spec(REPO / "specs" / "implement.md")
    plan = _authoring_plan()
    limit = int(RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM)
    for stem in CORE:
        ticket = _ticket(stem)
        rendered = spec.render({
            "workspace": DataBlock(
                "engine", f"stem: {stem}\nbranch: {stem}\n"
                f"run record: tickets/{stem}/{RUN_RECORD}\n"),
            "ticket": DataBlock("host", _path(stem).read_text()),
            "context": DataBlock("host", _context(ticket.context)),
        }, plan=plan, plan_sections=ticket.plan_sections, effort="max")
        assert len(rendered) <= limit, (stem, len(rendered), limit)


def test_invoker_governed_path_direct_lane_and_exact_trigger_contract():
    scope = " ".join(_section("retro-drain-invoker", "Scope in").split())
    criteria = " ".join(_section("retro-drain-invoker", "Acceptance criteria").split())
    for phrase in (
        "closed local `RetroArtifact`", "`LLMStage` named `retro`",
        "rendered from `specs/retro.md`", "existing `Driver`",
        "shared provider/cooldown payload", "`tickets/retro/<seq>.md`",
        "effect key is exactly `retro/<seq>`", "not a JSON artifact",
        "default-off retro hook", "`squatch/__main__.py::_drain`",
        "N=25", "M=7 days", "S=5", "top of every dispatch iteration",
        "at quiescence and immediately before dispatching any",
        "only if a merge landed after the latest completed",
        "`retro-failed/<window-boundary>/<trigger>`",
        "`{kind: retro_failed, window_boundary, trigger, error_code}`",
        "signature-deduped `failure_report`", "bounded redacted",
        "Only a later `retro/<seq>` effect completion releases suppression",
        "public read-only accessor", "explicit construction seam",
        "`RetroConstructionError`", "`Bench.drain()` directly",
    ):
        assert phrase in scope
    assert "zero-padded" in scope and "reserved `retro` directory" in scope
    assert "no unbounded retry" in criteria
    for suite in REGRESSION_SUITES:
        assert suite in OWNERSHIP["retro-drain-invoker"]
        assert f"`{suite}`" in scope
    for assertion_kind in (
        "transition-risk fence", "concrete non-firing reason",
        "ancestry-history assertion", "fake-call and spawned-main history assertions",
        "ordered pipeline-call and control-journal", "trip/report Box-count assertions",
        "process-call and cooldown-journal sequences", "provider/notification call lists",
        "dispatch-call/snapshot and pause-journal", "drain result and control-journal",
    ):
        assert assertion_kind in scope


def test_activation_identity_reopen_draft_bridge_and_merge_signal_contract():
    scope = " ".join(_section("retro-box-activation", "Scope in").split())
    criteria = " ".join(_section("retro-box-activation", "Acceptance criteria").split())
    for phrase in (
        "one `retro_finding` per", "`retro_report_key`", "`fixed_failure`",
        "`overcorrection_risk`", "`proposed_spec_paths`",
        "`proposal_id = sha256(canonical_json(retro_report_key, fixed_failure, overcorrection_risk, sorted(proposed_spec_paths)))[:16]`",
        "`retro-proposal/<retro_report_key>/<proposal_id>`", "one `record_rereport` path",
        "K=3", "`tombstone-reopen/<box_id>/<reports>`",
        "`{kind: tombstone_auto_reopened, box_id, signature, reports}` BEFORE clearing",
        "`reopened_from_tombstone: true`", "Every production Box constructor",
        "including Merge's existing Box construction", "Verification and base-failure",
        "never consulted for retro provenance", "`python -m squatch.box ingest`",
        "`RereportCallbackRequired`", "`rerun through a journal-backed Squatch command`",
        "`policy.starting_state`", "forces", "`draft`", "only after authoring succeeds",
        "`retro-ticket/<ticket-stem>`",
        "`{kind: retro_ticket_authored, box_id, retro_report_key, ticket_stem}`",
        "after the real squash SHA", "before the merged terminal",
        "source is exactly `box:retro_finding`", "under `specs/` ending in `.md`",
        "`retro-prompt-spec-change/<ticket-stem>/<squash-sha>`",
        "`{kind: retro_prompt_spec_change_merged, box_id, retro_report_key, ticket_stem, squash_sha, changed_spec_paths}`",
        "sorted non-empty tuple", "missing or ambiguous bridge is a hard merge",
    ):
        assert phrase in scope
    assert "replay idempotence" in scope
    assert "tests/test_status.py` does not yet exist" in scope
    for phrase in (
        "exact replay-stable `signal` key and body before clearing",
        "including Merge", "keeps the tombstone",
        "exact paved road", "journal-before-reopen", "journal-only Merge lookup",
    ):
        assert phrase in criteria


def test_scorecard_partition_and_fixed_finite_phase5_suffix():
    scope = " ".join(_section("phase5-continue", "Scope in").split())
    assert _admissions("phase5-continue") == SUFFIX
    assert all(1 <= len(row) <= 3 for row in SUFFIX)
    assert SUFFIX[-1] == ("phase5-exit",)
    assert "with no successor" in scope
    for phrase in (
        "then-merged `squatch/retro.py` and",
        "Context, or are", "individually named measured on-demand exceptions",
        "synthetic render fixtures only", "never compare",
        "Only `squatch/scorecard.py`, `tests/test_scorecard.py`, and",
        "`tests/test_seeded_phase5_02.py` are sibling-new",
        "already-merged", "`tests/test_seeded_phase4_05.py` continuation pattern",
        "new-in-this-admission `tests/test_seeded_phase5_01.py` is explicitly excluded",
        "`phase5-continue-03` depends on both feature stems",
        "`phase5-continue-04` depends on `retro-doctor-cli`",
        "KNOWN-HARD high/high `phase5-exit`",
    ):
        assert phrase in scope
    for later_path in (
        "squatch/scorecard.py", "tests/test_scorecard.py", "tests/test_seeded_phase5_02.py",
        "squatch/status.py", "tests/test_status.py", "squatch/baseline.py",
        "tests/test_baseline.py", "squatch/doctor.py", "tests/test_doctor.py",
        "tests/test_phase5_exit.py", "tests/test_seeded_phase6_core.py",
    ):
        assert f"`{later_path}`" in scope
