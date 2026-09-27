"""Kernel artifact types (SQUATCH_PLAN.md section 5).

Every stage consumes one typed artifact and emits one; this module holds the
shared shapes: the versioned, provenance-stamped `Artifact` base, the
`Finding` every gate emits, and the `StageResult` every stage returns.
Concrete artifact models (ticket, packing slip, invoice, ...) land with the
stage that first emits them; the ticket is the one artifact exempt from the
base fields (its provenance lives in the journal).
"""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ARTIFACT_SCHEMA_VERSION = 1

DAEMON_SOAK_REPORT = "daemon-soak-report.json"
DAEMON_SOAK_MEMBERS = (
    "worker_killed_mid_run",
    "conflict_resolution_rungs",
    "semantic_conflict_integration_red",
)
DaemonSoakMemberName = Literal[
    "worker_killed_mid_run",
    "conflict_resolution_rungs",
    "semantic_conflict_integration_red",
]

StageName = Literal["author", "implement", "check", "review", "rework", "merge", "triage", "retro"]
STAGE_NAMES: frozenset[str] = frozenset(StageName.__args__)
SUBSTEP_NAMES: frozenset[str] = frozenset({"diagnose"})

Outcome = Literal["ok", "already_satisfied", "invalid_artifact", "gate_failed", "premise_failed",
                  "timeout", "infra_error", "budget_exceeded"]
OUTCOMES: frozenset[str] = frozenset(Outcome.__args__)

# The closed RUN-STATE vocabulary a `state_transition` body's `to` carries
# (section 6): `running`, plus the terminals `merged`, `abandoned`,
# `rejected`, and each non-ok Outcome used as a terminal state name.
TERMINAL_RUN_STATES: frozenset[str] = frozenset({"merged", "abandoned", "rejected"}) | (OUTCOMES - {"ok"})
RUN_STATES: frozenset[str] = TERMINAL_RUN_STATES | {"running"}

# Engine-shipped gate codes (section 7 v1 set). Host review surfaces register
# more at config load; unlisted means stop.
GateCode = Literal["ticket_schema", "scope_fence", "verification", "run_record", "diff_budget",
                   "post_rebase_regate", "bug_evidence", "core_drift", "correctness_review",
                   "requisition_review"]
GATE_CODES: frozenset[str] = frozenset(GateCode.__args__)


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Artifact(ClosedModel):
    """Base of every stage-emitted artifact except the ticket.

    `artifact_schema_version` is the versioning-policy stamp: a reader refuses
    newer and tolerates older. The two provenance fields are invariant 1:
    the spec version and the HOST-repo commit the producing stage ran at.
    """

    artifact_schema_version: int = Field(default=ARTIFACT_SCHEMA_VERSION, ge=0)
    produced_by_spec_version: str = Field(min_length=1)
    produced_at_sha: str = Field(min_length=1)

    @field_validator("artifact_schema_version")
    @classmethod
    def _refuse_newer(cls, v: int) -> int:
        if v > ARTIFACT_SCHEMA_VERSION:
            raise ValueError(
                f"artifact_schema_version {v} is newer than this engine's "
                f"{ARTIFACT_SCHEMA_VERSION}; upgrade the engine")
        return v


class DaemonSoakEntry(ClosedModel):
    """One machine-observed member of the bounded Phase 3 daemon soak."""

    member: DaemonSoakMemberName
    fault: str = Field(min_length=1)
    observable: str = Field(min_length=1)
    expected: str = Field(min_length=1)
    observed: str = Field(min_length=1)
    disposition: Literal["box", "alert"]
    producing_run: str = Field(pattern=r"^[^/]+/\d+$")
    auditor: Literal["green", "red"]
    green: bool

    @model_validator(mode="after")
    def _green_is_derived(self):
        expected = self.observed == self.expected and self.auditor == "green"
        if self.green != expected:
            raise ValueError(
                "green must be true exactly when observed equals expected and auditor is green")
        return self


class DaemonSoakReport(ClosedModel):
    """Closed report emitted by the bounded, injected-clock daemon soak."""

    schema_version: Literal[1]
    produced_at_sha: str = Field(min_length=1)
    injected_hours: float = Field(ge=24)
    entries: tuple[DaemonSoakEntry, ...]

    @model_validator(mode="after")
    def _closed_member_list(self):
        members = tuple(entry.member for entry in self.entries)
        if members != DAEMON_SOAK_MEMBERS:
            raise ValueError(
                f"entries must contain the closed member list in order: {DAEMON_SOAK_MEMBERS}")
        return self


class Finding(ClosedModel):
    """One gate finding. `paved_road` is required: a finding that cannot say
    what to do instead is not a finding. `path`/`line` are nullable because a
    frontmatter- or schema-level finding has neither."""

    code: str = Field(min_length=1)
    path: str | None = None
    line: int | None = Field(default=None, ge=1)
    message: str = Field(min_length=1)
    paved_road: str = Field(min_length=1)


@dataclass(frozen=True)
class Cost:
    tokens: int
    seconds: float
    attempts: int
    # usd=0 and provider/model=None for non-LLM effects (section 6 ledger).
    usd: float = 0.0
    provider: str | None = None
    model: str | None = None


@dataclass(frozen=True)
class StageResult:
    outcome: Outcome
    artifact: Artifact | None
    findings: list[Finding]
    cost: Cost
    reason: str | None = None
