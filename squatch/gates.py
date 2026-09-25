"""Gate protocol, gate-lint, and the gate runner (SQUATCH_PLAN.md sections 5, 7).

A gate answers pass | fail with findings; it never decides its own severity.
The runner resolves hard/soft from config (`review.gate_severity`, invariant
3) over the shipped default in which every v1 hard-set code is hard, so an
unconfigured engine fails closed. Gate-lint runs before a gate ever executes:
a gate outside the closed protocol -- unlisted code, no paved road, no async
`check` -- is refused, never skipped.
"""

import inspect
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from pydantic import Field, model_validator

from squatch.artifacts import GATE_CODES, Artifact, Finding, ClosedModel
from squatch.config import Severity

Verdict = Literal["pass", "fail"]

# Shipped default (section 15): every engine-shipped code hard at merge.
SHIPPED_GATE_SEVERITY: Mapping[str, Severity] = {code: "hard" for code in sorted(GATE_CODES)}


class GateReport(ClosedModel):
    code: str = Field(min_length=1)
    verdict: Verdict
    findings: tuple[Finding, ...] = ()
    autofix_applied: bool = False

    @model_validator(mode="after")
    def _verdict_matches_findings(self):
        # A fail that names nothing is unactionable; a pass that names
        # something is a verdict the findings contradict.
        if (self.verdict == "fail") != bool(self.findings):
            raise ValueError(f"verdict {self.verdict!r} with {len(self.findings)} findings")
        return self


class Gate(Protocol):
    code: str
    # The road every finding of this gate can ship by default; gate-lint
    # refuses a gate without one.
    paved_road: str

    async def check(self, artifact: Artifact, workspace: Path) -> GateReport: ...


class GateError(Exception):
    """A gate defect the runner cannot route as a finding."""


class GateLintError(GateError):
    """The gate (or its report) is outside the closed protocol."""

    def __init__(self, gate: object, defects: list[str]):
        self.defects = defects
        super().__init__(f"{type(gate).__name__}: " + "; ".join(defects))


def gate_lint(gate: object) -> None:
    """Refuse a gate outside the closed protocol, naming every defect at once."""
    defects = []
    code = getattr(gate, "code", None)
    if code not in GATE_CODES:
        defects.append(f"code {code!r} is not an engine gate code")
    road = getattr(gate, "paved_road", None)
    if not isinstance(road, str) or not road.strip():
        defects.append("paved_road is missing or blank")
    check = getattr(gate, "check", None)
    if not inspect.iscoroutinefunction(check):
        defects.append("check is not an async method")
    if defects:
        raise GateLintError(gate, defects)


@dataclass(frozen=True)
class GateResult:
    report: GateReport
    severity: Severity

    @property
    def failed(self) -> bool:
        return self.report.verdict == "fail"


@dataclass(frozen=True)
class GateRun:
    results: tuple[GateResult, ...]

    @property
    def hard_failures(self) -> tuple[Finding, ...]:
        return self._failures("hard")

    @property
    def soft_failures(self) -> tuple[Finding, ...]:
        return self._failures("soft")

    @property
    def passed(self) -> bool:
        """No hard failure; soft failures go to the Suggestion Box and continue."""
        return not self.hard_failures

    def _failures(self, severity: Severity) -> tuple[Finding, ...]:
        return tuple(f for r in self.results if r.failed and r.severity == severity
                     for f in r.report.findings)


async def run_gates(gates: Iterable[Gate], artifact: Artifact, workspace: Path, *,
                    severity: Mapping[str, Severity] | None = None) -> GateRun:
    """Run every gate (never stopping early: re-prompt feedback wants every
    finding) and apply severity from config over the shipped default."""
    resolved = {**SHIPPED_GATE_SEVERITY, **(severity or {})}
    results = []
    for gate in gates:
        gate_lint(gate)
        try:
            report = await _check(gate, artifact, workspace)
        except GateError:
            raise  # a gate defect is the engine's bug, never a routable finding
        except Exception as e:  # a crashing gate fails closed
            report = GateReport(code=gate.code, verdict="fail", findings=(Finding(
                code=gate.code, message=f"gate crashed: {type(e).__name__}: {e}",
                paved_road=gate.paved_road),))
            results.append(GateResult(report, "hard"))
            continue
        results.append(GateResult(report, resolved[gate.code]))
    return GateRun(tuple(results))


async def _check(gate: Gate, artifact: Artifact, workspace: Path) -> GateReport:
    report = _linted(gate, await gate.check(artifact, workspace))
    if not report.autofix_applied:
        return report
    # Invariant 5: an autofix must be idempotent -- run twice, assert fixpoint.
    second = _linted(gate, await gate.check(artifact, workspace))
    if second.autofix_applied:
        raise GateError(f"{gate.code}: autofix is not idempotent (applied again on rerun)")
    return second.model_copy(update={"autofix_applied": True})


def _linted(gate: Gate, report: GateReport) -> GateReport:
    if not isinstance(report, GateReport) or report.code != gate.code:
        raise GateLintError(gate, [f"check returned a report for {getattr(report, 'code', report)!r}"])
    return report
