"""artifacts.py + gates.py: kernel artifact types and the gate runner (plan sections 5, 7).

The contract under test: every Finding ships a paved road (schema-required),
a Gate is a closed protocol that gate-lint checks BEFORE it ever runs, the
runner applies hard/soft severity from config (shipped default: every v1
hard-set code is hard), a crashing gate fails closed as hard, and an autofix
gate must reach a fixpoint on its second run (invariant 5).
"""

import pytest
from pydantic import ValidationError

from squatch.artifacts import (
    ARTIFACT_SCHEMA_VERSION,
    GATE_CODES,
    OUTCOMES,
    STAGE_NAMES,
    Artifact,
    Cost,
    Finding,
    StageResult,
)
from squatch.gates import (
    SHIPPED_GATE_SEVERITY,
    GateError,
    GateLintError,
    GateReport,
    gate_lint,
    run_gates,
)

PROVENANCE = {"produced_by_spec_version": "check@1", "produced_at_sha": "0123abcd"}


class Invoice(Artifact):
    """A stand-in concrete artifact; the real ones land with their stages."""

    commands_run: int = 0


def finding(code="run_record", **kw):
    base = {"message": "run record missing", "paved_road": "write run_record.json per section 13"}
    return Finding(code=code, **{**base, **kw})


class StubGate:
    """A well-formed gate whose verdict is scripted per call."""

    code = "run_record"
    paved_road = "write run_record.json per section 13"

    def __init__(self, *reports: GateReport):
        self.reports = list(reports)
        self.calls = 0

    async def check(self, artifact, workspace):
        self.calls += 1
        return self.reports.pop(0)


def passing(code="run_record"):
    return GateReport(code=code, verdict="pass")


def failing(code="run_record", **kw):
    return GateReport(code=code, verdict="fail", findings=[finding(code)], **kw)


# --- artifacts.py -----------------------------------------------------------


def test_finding_requires_a_paved_road():
    with pytest.raises(ValidationError):
        Finding(code="run_record", message="run record missing")
    with pytest.raises(ValidationError):
        finding(paved_road="")


def test_finding_path_and_line_are_optional():
    f = finding()
    assert f.path is None and f.line is None
    located = finding(path="squatch/x.py", line=7)
    assert (located.path, located.line) == ("squatch/x.py", 7)


def test_artifact_carries_version_and_provenance():
    a = Invoice(**PROVENANCE)
    assert a.artifact_schema_version == ARTIFACT_SCHEMA_VERSION
    assert a.produced_at_sha == "0123abcd"
    with pytest.raises(ValidationError):
        Invoice(produced_by_spec_version="check@1")  # provenance is required
    with pytest.raises(ValidationError):
        Invoice(**PROVENANCE, stray=1)  # closed shape


def test_artifact_refuses_newer_schema_and_tolerates_older():
    with pytest.raises(ValidationError):
        Invoice(**PROVENANCE, artifact_schema_version=ARTIFACT_SCHEMA_VERSION + 1)
    older = Invoice.model_validate({**PROVENANCE, "artifact_schema_version": ARTIFACT_SCHEMA_VERSION - 1})
    assert older.artifact_schema_version == ARTIFACT_SCHEMA_VERSION - 1


def test_closed_vocabularies():
    assert STAGE_NAMES == frozenset(
        {"author", "implement", "check", "review", "rework", "merge", "triage", "retro"})
    assert OUTCOMES == frozenset({
        "ok", "already_satisfied", "invalid_artifact", "gate_failed", "premise_failed",
        "timeout", "infra_error", "budget_exceeded"})
    assert GATE_CODES == frozenset({
        "ticket_schema", "scope_fence", "verification", "run_record", "diff_budget",
        "post_rebase_regate", "bug_evidence", "core_drift", "correctness_review",
        "requisition_review"})


def test_stage_result_is_a_frozen_record():
    r = StageResult(outcome="already_satisfied", artifact=None, findings=[],
                    cost=Cost(tokens=0, seconds=1.5, attempts=1))
    assert r.cost.usd == 0 and r.cost.provider is None and r.cost.model is None
    with pytest.raises(AttributeError):
        r.outcome = "ok"


# --- GateReport -------------------------------------------------------------


def test_gate_report_verdict_and_findings_agree():
    with pytest.raises(ValidationError):
        GateReport(code="run_record", verdict="fail")  # a fail that names nothing
    with pytest.raises(ValidationError):
        GateReport(code="run_record", verdict="pass", findings=[finding()])
    with pytest.raises(ValidationError):
        GateReport(code="run_record", verdict="warn", findings=[finding()])
    assert failing().autofix_applied is False


# --- gate-lint --------------------------------------------------------------


def test_gate_lint_accepts_a_well_formed_gate():
    gate_lint(StubGate())


def test_gate_lint_rejects_a_paved_road_less_gate():
    class NoRoad:
        code = "run_record"

        async def check(self, artifact, workspace):
            return passing()

    class BlankRoad(NoRoad):
        paved_road = "   "

    for gate in (NoRoad(), BlankRoad()):
        with pytest.raises(GateLintError) as e:
            gate_lint(gate)
        assert "paved_road" in str(e.value)


def test_gate_lint_rejects_an_unlisted_code():
    class Unlisted(StubGate):
        code = "style_nits"

    with pytest.raises(GateLintError) as e:
        gate_lint(Unlisted())
    assert "style_nits" in str(e.value)


def test_gate_lint_rejects_a_non_async_or_missing_check():
    class SyncCheck(StubGate):
        def check(self, artifact, workspace):
            return passing()

    class NoCheck:
        code = "run_record"
        paved_road = "x"

    for gate in (SyncCheck(), NoCheck()):
        with pytest.raises(GateLintError) as e:
            gate_lint(gate)
        assert "check" in str(e.value)


def test_gate_lint_reports_every_defect_at_once():
    class Broken:
        code = "nope"

    with pytest.raises(GateLintError) as e:
        gate_lint(Broken())
    text = str(e.value)
    assert "nope" in text and "paved_road" in text and "check" in text


# --- runner -----------------------------------------------------------------


def test_shipped_severity_is_every_gate_code_hard():
    assert set(SHIPPED_GATE_SEVERITY) == GATE_CODES
    assert set(SHIPPED_GATE_SEVERITY.values()) == {"hard"}


async def test_runner_defaults_to_hard(tmp_path):
    gate = StubGate(failing())
    run = await run_gates([gate], Invoice(**PROVENANCE), tmp_path)
    assert run.passed is False
    assert [f.code for f in run.hard_failures] == ["run_record"]
    assert run.soft_failures == ()
    assert run.results[0].severity == "hard"


async def test_runner_applies_soft_severity_from_config(tmp_path):
    run = await run_gates([StubGate(failing())], Invoice(**PROVENANCE), tmp_path,
                          severity={"run_record": "soft"})
    assert run.passed is True
    assert run.hard_failures == ()
    assert [f.code for f in run.soft_failures] == ["run_record"]


async def test_config_overrides_only_the_codes_it_names(tmp_path):
    class Fence(StubGate):
        code = "scope_fence"
        paved_road = "list the path in the ticket's scope fence"

    run = await run_gates([StubGate(failing()), Fence(failing("scope_fence"))],
                          Invoice(**PROVENANCE), tmp_path, severity={"run_record": "soft"})
    assert [r.severity for r in run.results] == ["soft", "hard"]
    assert run.passed is False


async def test_runner_runs_every_gate_and_hands_the_artifact_through(tmp_path):
    seen = []

    class Recorder(StubGate):
        async def check(self, artifact, workspace):
            seen.append((artifact, workspace))
            return await super().check(artifact, workspace)

    artifact = Invoice(**PROVENANCE)
    run = await run_gates([Recorder(failing()), Recorder(passing())], artifact, tmp_path)
    assert seen == [(artifact, tmp_path)] * 2
    assert [r.report.verdict for r in run.results] == ["fail", "pass"]


async def test_runner_refuses_to_run_a_gate_that_fails_lint(tmp_path):
    class NoRoad(StubGate):
        paved_road = ""

    gate = NoRoad(passing())
    with pytest.raises(GateLintError):
        await run_gates([gate], Invoice(**PROVENANCE), tmp_path)
    assert gate.calls == 0


async def test_runner_refuses_a_report_under_another_code(tmp_path):
    with pytest.raises(GateLintError):
        await run_gates([StubGate(passing("scope_fence"))], Invoice(**PROVENANCE), tmp_path)


async def test_a_crashing_gate_fails_closed_as_hard(tmp_path):
    class Crash(StubGate):
        async def check(self, artifact, workspace):
            raise RuntimeError("boom")

    run = await run_gates([Crash()], Invoice(**PROVENANCE), tmp_path,
                          severity={"run_record": "soft"})
    assert run.passed is False
    (f,) = run.hard_failures
    assert f.code == "run_record" and "boom" in f.message
    assert f.paved_road == StubGate.paved_road


async def test_autofix_reruns_to_a_fixpoint(tmp_path):
    gate = StubGate(failing(autofix_applied=True), passing())
    run = await run_gates([gate], Invoice(**PROVENANCE), tmp_path)
    assert gate.calls == 2
    (result,) = run.results
    assert result.report.verdict == "pass" and result.report.autofix_applied is True
    assert run.passed is True


async def test_autofix_that_never_settles_is_refused(tmp_path):
    gate = StubGate(failing(autofix_applied=True), failing(autofix_applied=True))
    with pytest.raises(GateError):
        await run_gates([gate], Invoice(**PROVENANCE), tmp_path)
