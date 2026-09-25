"""The failure spine's single diagnosis judgment (plan section 11.3)."""

from typing import Annotated

from pydantic import Field, field_validator, model_validator

from squatch.artifacts import OUTCOMES, Artifact, ClosedModel
from squatch.caps import DIAGNOSIS_CAP, consume, spent
from squatch.driver import Driver, LLMStage
from squatch.harvest import HARVEST_FILE, RUN_RECORD
from squatch.specs import DATA_MARKER, DataBlock, Spec, load_spec
from squatch.tickets import TICKET_FILE, TICKETS_DIR, Ticket

VERDICTS = frozenset({"retry", "escalate", "split", "reject", "abandon-human"})
DIAGNOSIS_CALLS = frozenset(
    {"ok", "synthetic", "skipped", "invalid_artifact", "infra_error", "timeout"})
DIAG_DIFF_CHARS = 20_000
DIAGNOSE_RETRY_CAP = 1
DIAGNOSIS_FILE = "diagnosis.json"

Lesson = Annotated[str, Field(min_length=1, max_length=300)]


class DiagnosisInput(Artifact):
    stem: str
    ticket: str
    harvest: str
    run_record: str | None = None
    diff: str | None = None
    prior_lessons: tuple[str, ...] = ()


class Diagnosis(Artifact):
    verdict: str
    lessons: tuple[Lesson, ...] = Field(min_length=1)
    reason: str = Field(min_length=1)

    @field_validator("verdict")
    @classmethod
    def _closed_verdict(cls, value: str) -> str:
        if value not in VERDICTS:
            raise ValueError(f"verdict must be one of {sorted(VERDICTS)}")
        return value

    @field_validator("reason")
    @classmethod
    def _one_line_reason(cls, value: str) -> str:
        if "\n" in value or "\r" in value:
            raise ValueError("reason must be one line")
        return value


class DiagnosisRecord(ClosedModel):
    run_seq: int = Field(ge=0)
    outcome: str
    call: str
    verdict: str | None
    lessons: tuple[str, ...]
    reason: str | None
    detail: str | None

    @field_validator("outcome")
    @classmethod
    def _closed_outcome(cls, value: str) -> str:
        if value not in OUTCOMES - {"ok", "already_satisfied"}:
            raise ValueError("diagnosis outcome must be a non-ok Outcome")
        return value

    @field_validator("call")
    @classmethod
    def _closed_call(cls, value: str) -> str:
        if value not in DIAGNOSIS_CALLS:
            raise ValueError(f"call must be one of {sorted(DIAGNOSIS_CALLS)}")
        return value

    @field_validator("verdict")
    @classmethod
    def _nullable_closed_verdict(cls, value: str | None) -> str | None:
        if value is not None and value not in VERDICTS:
            raise ValueError(f"verdict must be null or one of {sorted(VERDICTS)}")
        return value

    @model_validator(mode="after")
    def _reason_only_for_a_verdict(self):
        if self.call not in {"ok", "synthetic"} and self.reason is not None:
            raise ValueError("reason is null unless call is ok or synthetic")
        return self


def diagnose_stage(spec: Spec, *, tier: str, effort: str) -> LLMStage:
    """Build the pure diagnosis stage; construction needs no runtime services."""
    def render(inputs: DiagnosisInput, findings) -> str:
        blocks = {
            "ticket": DataBlock("host", inputs.ticket),
            "harvest": DataBlock("untrusted", inputs.harvest.replace(
                DATA_MARKER, "[squatch-data:")),
        }
        if inputs.run_record is not None:
            blocks["run_record"] = DataBlock(
                "untrusted", inputs.run_record.replace(DATA_MARKER, "[squatch-data:"))
        if inputs.diff:
            blocks["diff"] = DataBlock(
                "untrusted", inputs.diff.replace(DATA_MARKER, "[squatch-data:"))
        if inputs.prior_lessons:
            blocks["prior_lessons"] = DataBlock(
                "untrusted", ("\n".join(f"- {lesson}" for lesson in inputs.prior_lessons) + "\n")
                .replace(DATA_MARKER, "[squatch-data:"))
        return spec.render(blocks, findings=findings, effort=effort)

    return LLMStage(name="diagnose", surface=spec.surface, spec_version=spec.version,
                    tier=tier, effort=effort, consumes=DiagnosisInput, emits=Diagnosis,
                    gates=(), render=render)


class Diagnoser:
    """The terminal handler's one entry point for diagnosis."""

    def __init__(self, stages):
        self._repo = stages._repo
        self._config = stages._config
        self._git = stages._git
        self._llm = stages._llm
        self._effects = stages._effects
        self._spec = load_spec(stages._specs_dir / "diagnose.md")
        self._driver = Driver(
            llm=self._llm, spool=stages._spool,
            log=stages._log, clock=stages._clock, retry_cap=DIAGNOSE_RETRY_CAP,
            severity=self._config.review.gate_severity)

    async def diagnose(self, ticket: Ticket, delivery, *, run_seq: int) -> DiagnosisRecord:
        outcome = delivery.outcome
        if outcome in {"premise_failed", "budget_exceeded"}:
            return self._record(run_seq, outcome, "skipped",
                                detail=f"{outcome} terminals are not diagnosed")
        if (reason := spent(self._config, self._effects.journal.read(), ticket.stem)) is not None:
            return self._record(run_seq, outcome, "skipped", detail=reason)
        if not delivery.worktree.is_dir():
            detail = f"workspace missing: {delivery.worktree}"
            return self._record(run_seq, outcome, "synthetic", verdict="abandon-human",
                                lessons=(detail,), reason=detail)

        await consume(self._effects.journal, repo=self._repo, git=self._git, stem=ticket.stem,
                      cap=DIAGNOSIS_CAP, run_seq=run_seq)
        head = await self._git.rev_parse(self._repo, ticket.stem)
        inputs = await self._inputs(ticket, delivery, run_seq, head)
        stage = diagnose_stage(self._spec, tier=ticket.agent_tier, effort=ticket.agent_effort)
        result = await self._driver.run(
            stage, inputs, ticket=ticket.stem, run_seq=run_seq, attempt=run_seq,
            workspace=delivery.worktree, sha=head)
        if result.outcome == "ok":
            diagnosis: Diagnosis = result.artifact
            return self._record(run_seq, outcome, "ok", verdict=diagnosis.verdict,
                                lessons=diagnosis.lessons, reason=diagnosis.reason)
        call = result.outcome if result.outcome in DIAGNOSIS_CALLS else "invalid_artifact"
        return self._record(run_seq, outcome, call, detail=result.reason)

    async def _inputs(self, ticket: Ticket, delivery, run_seq: int, head: str) -> DiagnosisInput:
        root = self._repo / TICKETS_DIR / ticket.stem
        attempt = root / "attempts" / str(run_seq)
        harvest_path = attempt / HARVEST_FILE
        run_path = attempt / RUN_RECORD
        diff = (await self._git.diff(self._repo, delivery.base, ticket.stem)).replace(
            DATA_MARKER, "[squatch-data:")[:DIAG_DIFF_CHARS]
        return DiagnosisInput(
            stem=ticket.stem,
            ticket=(root / TICKET_FILE).read_text(),
            harvest=(harvest_path.read_text(errors="replace") if harvest_path.is_file()
                     else "(harvest unavailable)\n"),
            run_record=run_path.read_text(errors="replace") if run_path.is_file() else None,
            diff=diff or None,
            prior_lessons=self._prior_lessons(ticket.stem),
            produced_by_spec_version=self._spec.version, produced_at_sha=head)

    def _prior_lessons(self, stem: str) -> tuple[str, ...]:
        return tuple(
            lesson
            for event in self._effects.journal.read()
            if event.type == "state_transition" and event.ticket == stem
            for diagnosis in (event.body.get("diagnosis"),)
            if isinstance(diagnosis, dict) and diagnosis.get("verdict") is not None
            for lesson in diagnosis.get("lessons", ()))

    @staticmethod
    def _record(run_seq: int, outcome: str, call: str, *, verdict: str | None = None,
                lessons: tuple[str, ...] = (), reason: str | None = None,
                detail: str | None = None) -> DiagnosisRecord:
        return DiagnosisRecord(run_seq=run_seq, outcome=outcome, call=call, verdict=verdict,
                               lessons=lessons, reason=reason, detail=detail)
