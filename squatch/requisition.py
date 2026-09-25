"""Authored-ticket feasibility review (SQUATCH_PLAN.md sections 7, 9, 19)."""

import hashlib
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from pydantic import Field, field_validator, model_validator

from squatch import specs as specs_module
from squatch.artifacts import Artifact, ClosedModel, Finding
from squatch.config import Tier
from squatch.driver import Driver, LLMStage, Spool
from squatch.effects import effect_key
from squatch.enginelog import EngineLog
from squatch.gates import GateReport
from squatch.git import Git, GitError
from squatch.llm import Effort, LLMRequest, LLMResult
from squatch.llmeffect import COST_FIELDS, LLMEffect
from squatch.seams import Clock
from squatch.specs import DataBlock, RenderRefused, Spec, load_spec, resolve_plan_sections
from squatch.stages import SPECS_DIR, Stages
from squatch.tickets import (PLAN_FILE, TICKET_FILE, TICKETS_DIR, Ticket, lint_ticket,
                             on_disk_stems, parse_frontmatter)

REQ_FILE_CHARS = 12000
REQ_PLANE_CHARS = 20000
REQ_RENDER_HEADROOM = 0.75
REQ_RETRY_CAP = 1
REVIEW_CODE = "requisition_review"
SHRINK_ROAD = "shrink the inputs or split the ticket"
PLAN_DEFECT_ROAD = "fix the plan, then re-author the ticket"

_OVER_BOUND = re.compile(r"rendered prompt is (\d+) chars, over the (\d+)-char bound")


class RenderMeasure(ClosedModel):
    chars: int = Field(ge=0)
    bound: int = Field(gt=0)
    headroom: float = Field(gt=0, le=1)
    over: bool


class FenceFact(ClosedModel):
    path: str = Field(min_length=1)
    exists_on_main: bool


class RequisitionInput(Artifact):
    stem: str = Field(min_length=1)
    ticket: str = Field(min_length=1)
    context_files: tuple[tuple[str, str], ...]
    plan_sections: tuple[tuple[str, str], ...]
    plane: str
    render_measure: RenderMeasure
    fence_facts: tuple[FenceFact, ...]


class RequisitionVerdict(Artifact):
    verdict: Literal["approve", "snag", "rma"]
    summary: str = Field(min_length=1)
    findings: tuple[Finding, ...]

    @field_validator("findings")
    @classmethod
    def _finding_codes_are_closed(cls, findings: tuple[Finding, ...]) -> tuple[Finding, ...]:
        if any(finding.code != REVIEW_CODE for finding in findings):
            raise ValueError(f"every finding code must be {REVIEW_CODE!r}")
        return findings

    @model_validator(mode="after")
    def _findings_match_verdict(self):
        if (self.verdict == "approve") != (not self.findings):
            raise ValueError("findings is [] exactly when verdict is approve")
        return self

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        if cls is RequisitionVerdict and isinstance(obj, Mapping):
            emitted = REQUISITION_EMITS.get(obj.get("verdict"))
            if emitted is not None:
                return emitted.model_validate(obj, *args, **kwargs)
        return super().model_validate(obj, *args, **kwargs)


class RequisitionApprove(RequisitionVerdict):
    verdict: Literal["approve"]


class RequisitionSnag(RequisitionVerdict):
    verdict: Literal["snag"]


class RequisitionRMA(RequisitionVerdict):
    verdict: Literal["rma"]


REQUISITION_EMITS: Mapping[str, type[RequisitionVerdict]] = {
    "approve": RequisitionApprove,
    "snag": RequisitionSnag,
    "rma": RequisitionRMA,
}
Verdict = RequisitionApprove | RequisitionSnag | RequisitionRMA


@dataclass(frozen=True)
class RequisitionStage(LLMStage):
    """The driver's branch stage: one schema dispatcher, three concrete emits."""

    emits_by_verdict: Mapping[str, type[RequisitionVerdict]]

    def __post_init__(self):
        if self.name != REVIEW_CODE or self.surface != REVIEW_CODE:
            raise ValueError("the requisition stage name and surface must be requisition_review")


def requisition_stage(spec: Spec, *, tier: Tier, effort: Effort) -> RequisitionStage:
    expected = {name: artifact.__name__ for name, artifact in REQUISITION_EMITS.items()}
    if (spec.surface != REVIEW_CODE or spec.consumes != "RequisitionInput"
            or spec.emits != expected or spec.gates):
        raise ValueError("requisition_review spec does not match the stage contract")

    def render(inputs: RequisitionInput, findings: Sequence[Finding]) -> str:
        context = "\n\n".join(
            f"### {path}\n{content}" for path, content in inputs.context_files)
        sections = "".join(body for _, body in inputs.plan_sections)
        fence = "\n".join(
            f"{fact.path}: exists_on_main={str(fact.exists_on_main).lower()}"
            for fact in inputs.fence_facts)
        return spec.render({
            "ticket": DataBlock("host", inputs.ticket),
            "context_files": DataBlock("host", context or "(none)"),
            "plan_sections": DataBlock("engine", sections or "(none)"),
            "plane": DataBlock("engine", inputs.plane),
            "render_measure": DataBlock(
                "engine", inputs.render_measure.model_dump_json(indent=2)),
            "fence_facts": DataBlock("engine", fence or "(none)"),
        }, findings=findings, effort=effort)

    return RequisitionStage(
        name=REVIEW_CODE, surface=REVIEW_CODE, spec_version=spec.version,
        tier=tier, effort=effort, consumes=RequisitionInput,
        emits=RequisitionVerdict, gates=(), render=render,
        emits_by_verdict=REQUISITION_EMITS)


class _KeyedLLMEffect:
    """Use LLMEffect's call body under requisition's content-addressed key."""

    def __init__(self, base: LLMEffect, stem: str, text_sha: str, call_seq_base: int):
        self._base = base
        self.effects = base.effects
        self.stuck_seconds = base.stuck_seconds
        self._stem = stem
        self._text_sha = text_sha
        self._call_seq_base = call_seq_base
        self.last_reply: str | None = None

    async def call(self, req: LLMRequest, *, stem: str, run_seq: int, attempt: int,
                   call_seq: int) -> LLMResult:
        sequence = self._call_seq_base + call_seq
        key = effect_key("llm", REVIEW_CODE, self._stem, self._text_sha, sequence)

        async def action() -> dict:
            raw_call = LLMEffect._call.__wrapped__
            return await raw_call(
                self._base, req, stem=stem, run_seq=run_seq,
                attempt=attempt, call_seq=call_seq)

        data = await self.effects.run(
            action, key=key, ticket=self._stem,
            cost=lambda result: {name: result[name] for name in COST_FIELDS})
        result = LLMResult(**data)
        self.last_reply = result.text
        return result


class RequisitionReview:
    def __init__(self, *, repo: Path, git: Git, stages: Stages, llm: LLMEffect,
                 spool: Spool, log: EngineLog, clock: Clock,
                 spec: Spec | None = None):
        self._repo = Path(repo)
        self._git = git
        self._stages = stages
        self._llm = llm
        self._spool = spool
        self._log = log
        self._clock = clock
        self.spec = spec or load_spec(SPECS_DIR / "requisition_review.md")

    async def review(self, stem: str, text: str, *, run_seq: int,
                     call_seq_base: int) -> Verdict:
        ticket = self._ticket(stem, text)
        sha = await self._git.rev_parse(self._repo, "main")
        try:
            inputs = await self._inputs(ticket, text, sha)
        except RenderRefused as error:
            return self._render_refused(error, sha)
        if inputs.render_measure.over:
            measure = inputs.render_measure
            return RequisitionSnag(
                verdict="snag", summary="the base Implement render exceeds authoring headroom",
                findings=(Finding(
                    code=REVIEW_CODE,
                    message=(f"base Implement render is {measure.chars} chars against the "
                             f"{measure.bound}-char max-effort bound at "
                             f"{measure.headroom:.0%} headroom"),
                    paved_road=SHRINK_ROAD),),
                produced_by_spec_version=self.spec.version, produced_at_sha=sha)

        text_sha = _blob_sha(text)[:12]
        keyed = _KeyedLLMEffect(self._llm, stem, text_sha, call_seq_base)
        driver = Driver(
            llm=cast(LLMEffect, keyed), spool=self._spool, log=self._log,
            clock=self._clock, retry_cap=REQ_RETRY_CAP)
        try:
            result = await driver.run(
                requisition_stage(
                    self.spec, tier=cast(Tier, ticket.agent_tier),
                    effort=cast(Effort, ticket.agent_effort)),
                inputs, ticket=stem, run_seq=run_seq, attempt=run_seq,
                workspace=self._repo, sha=sha)
        except RenderRefused as error:
            return self._render_refused(error, sha)
        if result.outcome == "ok" and isinstance(result.artifact, RequisitionVerdict):
            return cast(Verdict, result.artifact)
        if result.outcome == "invalid_artifact":
            reply = keyed.last_reply or "(no reply recorded)"
            detail = f"invalid requisition_review reply: {reply[:500]!r}"
        else:
            detail = result.reason or result.outcome
        return RequisitionRMA(
            verdict="rma", summary="the feasibility review failed closed",
            findings=(Finding(code=REVIEW_CODE, message=detail,
                              paved_road=PLAN_DEFECT_ROAD),),
            produced_by_spec_version=self.spec.version, produced_at_sha=sha)

    def _render_refused(self, error: RenderRefused, sha: str) -> RequisitionSnag:
        road = ("remove the delimiter-carrying file from Context"
                if error.reason == "delimiter" else error.paved_road)
        return RequisitionSnag(
            verdict="snag", summary="the authored ticket cannot render safely",
            findings=(Finding(
                code=REVIEW_CODE,
                message=f"base Implement render refused ({error.reason}): {error}",
                paved_road=road),),
            produced_by_spec_version=self.spec.version, produced_at_sha=sha)

    def _ticket(self, stem: str, text: str) -> Ticket:
        plan = (self._repo / PLAN_FILE).read_text()
        return lint_ticket(
            text, stem=stem, repo=self._repo, plan=plan,
            resolve_stem=lambda candidate: (
                self._repo / TICKETS_DIR / candidate / TICKET_FILE).is_file())

    async def _inputs(self, ticket: Ticket, text: str, sha: str) -> RequisitionInput:
        plan = (self._repo / PLAN_FILE).read_text()
        sections = resolve_plan_sections(plan, ticket.plan_sections)
        context = tuple(
            (path, (self._repo / path).read_text(errors="replace")[:REQ_FILE_CHARS])
            for path in ticket.context)
        measure = self._measure(ticket, text)
        facts = []
        for path in ticket.scope_fence:
            try:
                await self._git.rev_parse(self._repo, f"main:{path}")
            except GitError:
                exists = False
            else:
                exists = True
            facts.append(FenceFact(path=path, exists_on_main=exists))
        return RequisitionInput(
            stem=ticket.stem, ticket=text, context_files=context,
            plan_sections=sections, plane=await self._plane(),
            render_measure=measure, fence_facts=tuple(facts),
            produced_by_spec_version="ticket", produced_at_sha=sha)

    def _measure(self, ticket: Ticket, text: str) -> RenderMeasure:
        bound = specs_module.RENDER_BOUND_CHARS["max"]
        try:
            chars = len(self._stages.render_implement(
                ticket, effort="max", ticket_text=text))
        except RenderRefused as error:
            if error.reason != "over_bound" or not (match := _OVER_BOUND.search(str(error))):
                raise
            chars = int(match.group(1))
        return RenderMeasure(
            chars=chars, bound=bound, headroom=REQ_RENDER_HEADROOM,
            over=chars > bound * REQ_RENDER_HEADROOM)

    async def _plane(self) -> str:
        merged = {
            event.ticket for event in self._llm.effects.journal.read()
            if event.type == "state_transition" and event.body.get("to") == "merged"
            and event.ticket}
        rows = []
        for stem in on_disk_stems(self._repo):
            rel = f"{TICKETS_DIR}/{stem}/{TICKET_FILE}"
            try:
                await self._git.rev_parse(self._repo, f"main:{rel}")
            except GitError:
                continue
            text = (self._repo / rel).read_text(errors="replace")
            meta, _ = parse_frontmatter(text)
            state = "" if stem in merged else f" [{meta.get('state', 'unknown')}]"
            rows.append(f"{stem}{state}: {_goal(text)}")
        return _cut_lines(rows, REQ_PLANE_CHARS)


TargetResolver = Callable[[Artifact, Path], Sequence[tuple[str, str]]]


class RequisitionGate:
    code = REVIEW_CODE
    paved_road = "re-author the ticket until requisition_review approves it"

    def __init__(self, review: RequisitionReview, targets: TargetResolver, *,
                 run_seq: int = 0, call_seq_base: int = 0):
        self._review = review
        self._targets = targets
        self._run_seq = run_seq
        self._call_seq_base = call_seq_base

    async def check(self, artifact: Artifact, workspace: Path) -> GateReport:
        findings = []
        for stem, text in self._targets(artifact, workspace):
            verdict = await self._review.review(
                stem, text, run_seq=self._run_seq,
                call_seq_base=self._call_seq_base)
            if isinstance(verdict, RequisitionApprove):
                continue
            for finding in verdict.findings:
                if isinstance(verdict, RequisitionRMA):
                    finding = finding.model_copy(update={"paved_road": PLAN_DEFECT_ROAD})
                findings.append(finding)
        return GateReport(
            code=self.code, verdict="fail" if findings else "pass",
            findings=tuple(findings))


def _blob_sha(text: str) -> str:
    data = text.encode()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def _goal(text: str) -> str:
    lines = text.splitlines()
    try:
        start = lines.index("## Goal") + 1
    except ValueError:
        return "(no Goal line)"
    return next((line.strip() for line in lines[start:]
                 if line.strip() and not line.startswith("## ")), "(no Goal line)")


def _cut_lines(lines: Sequence[str], limit: int) -> str:
    kept = []
    size = 0
    for line in lines:
        added = len(line) + (1 if kept else 0)
        if size + added > limit:
            break
        kept.append(line)
        size += added
    return "\n".join(kept) or "(none)"
