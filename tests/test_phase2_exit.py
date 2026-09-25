"""The Phase 2 exit reads committed evidence (SQUATCH_PLAN.md section 19)."""

from pathlib import Path

from squatch.shakeout import ShakeoutReport
from squatch.stages import Invoice

REPO = Path(__file__).resolve().parent.parent

GROUPS = (
    "shakeout-tickets",
    "shakeout-stages",
    "shakeout-driver",
    "shakeout-reconcile",
    "shakeout-merge",
    "shakeout-providers",
    "shakeout-drain",
    "shakeout-ladder",
)

MEMBERS = (
    "shakeout-tickets.bad_schema",
    "shakeout-stages.scope_escape",
    "shakeout-stages.premise_false",
    "shakeout-stages.branch_only_red",
    "shakeout-stages.base_red_excused",
    "shakeout-stages.empty_diff",
    "shakeout-stages.review_reject",
    "shakeout-stages.reject_reentry_criteria_position",
    "shakeout-stages.timeout_dead_ends",
    "shakeout-stages.secret_not_persisted",
    "shakeout-driver.schema_invalid_exhausts_reprompt",
    "shakeout-driver.stuck_budget_killed",
    "shakeout-reconcile.engine_death_reaped",
    "shakeout-merge.conflicted_rebase_aborted",
    "shakeout-providers.auth_expiry_classified",
    "shakeout-drain.red_then_green_one_invocation",
    "shakeout-drain.premise_park_released_by_edit",
    "shakeout-ladder.identical_terminals_climb",
    "shakeout-ladder.identical_terminals_reject_when_exhausted",
)


def test_committed_shakeout_report_closes_the_phase2_battery():
    path = REPO / "tickets" / "shakeout-ladder" / "shakeout-report.json"
    report = ShakeoutReport.model_validate_json(path.read_text())

    assert report.groups == GROUPS
    assert tuple(entry.member for entry in report.entries) == MEMBERS
    for entry in report.entries:
        assert entry.green is True, entry.member
        assert entry.auditor == "green", entry.member


def test_committed_invariant_auditor_invoice_passes():
    path = REPO / "tickets" / "invariant-auditor" / "checks.json"
    invoice = Invoice.model_validate_json(path.read_text())

    assert invoice.stem == "invariant-auditor"
    assert invoice.passed is True
