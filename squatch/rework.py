"""Dormant Rework boundary for unresolved merge admissions (plan section 20).

Rework consumes the merge queue's post-unwind handoff, asks the model for one
composite order, validates every ticket before writing any of them, and then
applies update, split, and escalation elements.  Activation and daemon wiring
belong to a later boundary.
"""

from dataclasses import dataclass
from pathlib import Path

from pydantic import Field, field_validator, model_validator

from squatch.artifacts import Artifact, ClosedModel, Finding, StageResult
from squatch.diagnose import DiagnosisRecord, Lesson
from squatch.driver import Driver, LLMStage
from squatch.gates import GateReport
from squatch.journal import Journal
from squatch.mergequeue import MergeQueue, UnresolvedConflictHandoff
from squatch.seams import Filesystem
from squatch.specs import DataBlock, Spec
from squatch.tickets import (PLAN_FILE, STEM, TICKET_FILE, TICKETS_DIR,
                             TicketLintError, lint_ticket)

SUPERSEDES_SIGNAL = "supersedes"


class ReworkInput(Artifact):
    handoff: UnresolvedConflictHandoff
    ticket: str


class UpdatedTicket(ClosedModel):
    ticket: str = Field(min_length=1)


class SplitTicket(ClosedModel):
    stem: str
    ticket: str = Field(min_length=1)

    @field_validator("stem")
    @classmethod
    def _valid_stem(cls, value: str) -> str:
        if not STEM.match(value):
            raise ValueError("stem must be lowercase kebab-case")
        return value


class ReworkEscalation(ClosedModel):
    lessons: tuple[Lesson, ...] = Field(min_length=1)
    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def _one_line_reason(cls, value: str) -> str:
        if "\n" in value or "\r" in value:
            raise ValueError("reason must be one line")
        return value


class ReworkOrder(Artifact):
    """One composite order; any non-empty combination is valid."""

    updated_ticket: UpdatedTicket | None = None
    split_tickets: tuple[SplitTicket, ...] = ()
    escalation: ReworkEscalation | None = None

    @model_validator(mode="after")
    def _has_work(self):
        if self.updated_ticket is None and not self.split_tickets and self.escalation is None:
            raise ValueError("a rework order must update, split, and/or escalate")
        stems = [ticket.stem for ticket in self.split_tickets]
        if len(stems) != len(set(stems)):
            raise ValueError("split ticket stems must be unique")
        return self


def rework_stage(spec: Spec, *, tier: str, effort: str, gates=()) -> LLMStage:
    """Build the pure model stage; runtime application remains in ``Rework``."""

    def render(inputs: ReworkInput, findings) -> str:
        return spec.render({
            "handoff": DataBlock("engine", inputs.handoff.model_dump_json(indent=2)),
            "ticket": DataBlock("host", inputs.ticket),
        }, findings=findings, effort=effort)

    return LLMStage(
        name="rework", surface=spec.surface, spec_version=spec.version,
        tier=tier, effort=effort, consumes=ReworkInput, emits=ReworkOrder,
        gates=tuple(gates), render=render)


class ReworkOrderGate:
    """Validate a whole order before Rework exposes any partial ticket set."""

    code = "ticket_schema"
    paved_road = "emit complete lint-valid tickets using only the closed ticket schema"

    def __init__(self, repo: Path, handoff: UnresolvedConflictHandoff):
        self._repo = Path(repo)
        self._handoff = handoff

    async def check(self, order: ReworkOrder, workspace: Path) -> GateReport:
        findings: list[Finding] = []
        children = {ticket.stem for ticket in order.split_tickets}
        if self._handoff.stem in children:
            findings.append(self._finding(
                f"split ticket stem {self._handoff.stem!r} is the superseded stem",
                "give every split child a fresh stem"))
        for child in order.split_tickets:
            if self._path(child.stem).exists():
                findings.append(self._finding(
                    f"split ticket stem {child.stem!r} already exists",
                    "give every split child a fresh stem"))

        candidates = []
        if order.updated_ticket is not None:
            candidates.append((self._handoff.stem, order.updated_ticket.ticket))
        candidates.extend((child.stem, child.ticket) for child in order.split_tickets)
        plan_path = self._repo / PLAN_FILE
        plan = plan_path.read_text() if plan_path.is_file() else None
        resolve = lambda stem: stem in children or self._path(stem).is_file()
        for stem, text in candidates:
            try:
                lint_ticket(text, stem=stem, repo=self._repo, plan=plan,
                            resolve_stem=resolve)
            except TicketLintError as error:
                findings.extend(error.findings)
        return GateReport(code=self.code, verdict="fail" if findings else "pass",
                          findings=tuple(findings))

    def _path(self, stem: str) -> Path:
        return self._repo / TICKETS_DIR / stem / TICKET_FILE

    def _finding(self, message: str, paved_road: str) -> Finding:
        return Finding(code=self.code, message=message, paved_road=paved_road)


@dataclass(frozen=True)
class ReworkResult:
    outcome: str
    handoff: UnresolvedConflictHandoff
    order: ReworkOrder | None
    diagnosis: DiagnosisRecord | None
    findings: tuple[Finding, ...] = ()


class Rework:
    """Consume one post-admission handoff and apply its validated order."""

    def __init__(self, *, repo: Path, queue: MergeQueue, journal: Journal,
                 fs: Filesystem, driver: Driver, spec: Spec,
                 tier: str, effort: str):
        self._repo = Path(repo)
        self._queue = queue
        self._journal = journal
        self._fs = fs
        self._driver = driver
        self._spec = spec
        self._tier = tier
        self._effort = effort

    async def run(self, *, sha: str) -> ReworkResult:
        # MergeQueue publishes only after its admission lock has unwound.  The
        # handoff is imported unchanged so its literal approval flag survives.
        handoff = await self._queue.next_rework()
        ticket = self._path(handoff.stem).read_text()
        inputs = ReworkInput(
            handoff=handoff, ticket=ticket,
            produced_by_spec_version=self._spec.version, produced_at_sha=sha)
        stage = rework_stage(
            self._spec, tier=self._tier, effort=self._effort,
            gates=(ReworkOrderGate(self._repo, handoff),))
        result: StageResult = await self._driver.run(
            stage, inputs, ticket=handoff.stem, run_seq=handoff.run_seq,
            attempt=handoff.run_seq, workspace=self._repo, sha=sha)
        if result.outcome != "ok":
            return ReworkResult(result.outcome, handoff, None, None,
                                tuple(result.findings))

        order: ReworkOrder = result.artifact
        self._apply(handoff, order)
        diagnosis = self._diagnosis(handoff, order.escalation)
        return ReworkResult("ok", handoff, order, diagnosis, tuple(result.findings))

    def _apply(self, handoff: UnresolvedConflictHandoff, order: ReworkOrder) -> None:
        if order.updated_ticket is not None:
            self._fs.write(self._path(handoff.stem), order.updated_ticket.ticket.encode())
        for child in order.split_tickets:
            self._fs.write(self._path(child.stem), child.ticket.encode())
        if order.split_tickets:
            stems = [child.stem for child in order.split_tickets]
            self._journal.append(
                "signal", {"kind": SUPERSEDES_SIGNAL,
                           "supersedes": {handoff.stem: stems}},
                ticket=handoff.stem,
                key=f"{SUPERSEDES_SIGNAL}/{handoff.stem}/{handoff.run_seq}")

    @staticmethod
    def _diagnosis(handoff: UnresolvedConflictHandoff,
                   escalation: ReworkEscalation | None) -> DiagnosisRecord | None:
        if escalation is None:
            return None
        return DiagnosisRecord(
            run_seq=handoff.run_seq, outcome="gate_failed", call="synthetic",
            verdict="escalate", lessons=escalation.lessons,
            reason=escalation.reason, detail=None)

    def _path(self, stem: str) -> Path:
        return self._repo / TICKETS_DIR / stem / TICKET_FILE
