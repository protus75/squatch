"""Grammar-gated Author stage for triaged Suggestion Box messages."""

from collections.abc import Callable, Sequence
from pathlib import Path

from pydantic import Field, field_validator

from squatch.artifacts import Artifact
from squatch.box import Box, Message
from squatch.config import Config
from squatch.driver import Driver, LLMStage, Spool
from squatch.effects import Effects
from squatch.enginelog import EngineLog
from squatch.git import Git, GitError
from squatch.journal import Journal
from squatch.llm import LLM
from squatch.llmeffect import LLMEffect
from squatch.policy import go_binds, starting_state
from squatch.redact import Redactor
from squatch.requisition import (REVIEW_CODE, RequisitionGate, RequisitionRMA,
                                 RequisitionReview, RequisitionSnag, Verdict)
from squatch.seams import Clock, Filesystem
from squatch.specs import DATA_MARKER, DataBlock, Spec, resolve_plan_sections
from squatch.stages import Stages
from squatch.tickets import (PLAN_FILE, STEM, TICKET_FILE, TICKETS_DIR, Intake,
                             TicketSchemaGate, lint_ticket, on_disk_stems, parse_frontmatter)
from squatch.triage import TriageAuthor

AUTHOR_PLANE_CHARS = 20000
AUTHOR_TREE_CHARS = 20000
AUTHOR_STUCK_SECONDS = 900
AUTHOR_RMA_ROAD = "fix the plan (or the message) and re-run squatch triage"


class AuthorInput(Artifact):
    message_id: str
    message_class: str
    summary: str
    detail: str
    origin: str
    triage: TriageAuthor
    ticket_contract: str
    plane: str
    tree: str
    context_files: str = ""


class AuthoredTicket(Artifact):
    stem: str
    ticket: str = Field(min_length=1)

    @field_validator("stem")
    @classmethod
    def _valid_stem(cls, value: str) -> str:
        if not STEM.match(value):
            raise ValueError("stem must match ^[a-z0-9][a-z0-9-]{1,63}$")
        return value


class _AuthorSchemaGate(TicketSchemaGate):
    """Expose the admitted artifact to the following feasibility gate."""

    def __init__(self, reset_review: Callable[[], None]):
        self._targets: tuple[tuple[str, str], ...] = ()
        self._reset_review = reset_review

    async def check(self, artifact: Artifact, workspace: Path):
        self._targets = ()
        self._reset_review()
        report = await super().check(artifact, workspace)
        if report.verdict == "pass":
            self._targets = ((artifact.stem, artifact.ticket),)
        return report

    def targets(self, artifact: Artifact, workspace: Path) -> tuple[tuple[str, str], ...]:
        return self._targets


def author_stage(spec: Spec, review: RequisitionReview, *, run_seq: int = 0) -> LLMStage:
    if (spec.surface != "author" or spec.consumes != "AuthorInput"
            or spec.emits != "AuthoredTicket"
            or spec.gates != ("ticket_schema", REVIEW_CODE)):
        raise ValueError("author spec does not match the Author stage contract")

    def render(inputs: AuthorInput, findings: Sequence) -> str:
        message = (f"id: {inputs.message_id}\nmessage_class: {inputs.message_class}\n"
                   f"summary: {inputs.summary}\ndetail: {inputs.detail}\n"
                   f"origin: {inputs.origin}\n")
        blocks = {
            "message": DataBlock("untrusted", _quoted(message)),
            "triage": DataBlock("engine", inputs.triage.model_dump_json(indent=2)),
            "ticket_contract": DataBlock("engine", inputs.ticket_contract),
            "plane": DataBlock("engine", inputs.plane),
            "tree": DataBlock("engine", inputs.tree),
        }
        if inputs.context_files:
            blocks["context_files"] = DataBlock("host", _quoted(inputs.context_files))
        return spec.render(blocks, findings=findings)

    schema = _AuthorSchemaGate(getattr(review, "reset", lambda: None))
    return LLMStage(name="author", surface=spec.surface, spec_version=spec.version,
                    tier=spec.tier, effort=spec.effort, consumes=AuthorInput,
                    emits=AuthoredTicket, gates=(
                        schema,
                        RequisitionGate(review, schema.targets, run_seq=run_seq),
                    ), render=render)


class _RenderOnlyProcess:
    """The feasibility review renders Implement but never executes a command."""

    async def run(self, *args, **kwargs):
        raise AssertionError("the Author feasibility renderer must not execute a process")


class _ReviewCapture:
    def __init__(self, review: RequisitionReview):
        self._review = review
        self.last: Verdict | None = None

    def reset(self) -> None:
        self.last = None

    async def review(self, *args, **kwargs) -> Verdict:
        self.last = await self._review.review(*args, **kwargs)
        return self.last


class Author:
    """The one machine-authoring entry point used by the triage consumer."""

    def __init__(self, *, repo: Path, config: Config, git: Git, fs: Filesystem, clock: Clock,
                 journal: Journal, llm: LLM, log: EngineLog, redact: Redactor,
                 report: Callable[[str], None]):
        self._repo = Path(repo)
        self._config = config
        self._git = git
        self._fs = fs
        self._clock = clock
        self._journal = journal
        self._llm = llm
        self._log = log
        self._redact = redact
        self._report = report
        self._box = Box(self._repo / config.state_dir, fs=fs, clock=clock)

    async def run(self, spec: Spec, message: Message, verdict: TriageAuthor, *,
                  pass_number: int, sha: str) -> str | None:
        try:
            bug_origin, has_repro = _policy_inputs(message)
        except ValueError as e:
            self._report_failure(message, e)
            return None
        inputs = await self._inputs(message, verdict, sha)
        state_dir = self._repo / self._config.state_dir
        effect = LLMEffect(llm=self._llm, effects=Effects(self._journal), redact=self._redact,
                           stuck_seconds=AUTHOR_STUCK_SECONDS, clock=self._clock)
        spool = Spool(state_dir, fs=self._fs, redact=self._redact)
        driver = Driver(
            llm=effect, spool=spool,
            log=self._log, clock=self._clock, retry_cap=self._config.caps.retry)
        stages = Stages(
            repo=self._repo, config=self._config, git=self._git,
            process=_RenderOnlyProcess(), fs=self._fs, llm=effect, log=self._log,
            redact=self._redact, clock=self._clock, env={})
        review = _ReviewCapture(RequisitionReview(
            repo=self._repo, git=self._git, stages=stages, llm=effect,
            spool=spool, log=self._log, clock=self._clock))
        result = await driver.run(
            author_stage(spec, review, run_seq=pass_number), inputs, ticket=None,
            run_seq=pass_number, attempt=message.seq, workspace=self._repo, sha=sha,
            terminal_findings=lambda findings: isinstance(review.last, RequisitionRMA))
        if result.outcome != "ok" or not isinstance(result.artifact, AuthoredTicket):
            if (isinstance(review.last, (RequisitionSnag, RequisitionRMA))
                    and result.findings
                    and all(finding.code == REVIEW_CODE for finding in result.findings)):
                self._record_review(message, review.last)
            if isinstance(review.last, RequisitionRMA):
                self._report(
                    f"author: {message.id}: rma; {review.last.summary}; left pending; "
                    f"{AUTHOR_RMA_ROAD}")
                return None
            detail = result.reason or result.outcome
            if result.reason == "retry cap spent":
                detail = f"retry allowance of {self._config.caps.retry} spent"
            self._report(f"author: {message.id}: {result.outcome}; {detail}; left pending")
            return None

        authored = result.artifact
        path = self._repo / TICKETS_DIR / authored.stem / TICKET_FILE
        try:
            parsed = lint_ticket(
                authored.ticket, stem=authored.stem, repo=self._repo,
                plan=(self._repo / PLAN_FILE).read_text(),
                resolve_stem=lambda stem: (
                    self._repo / TICKETS_DIR / stem / TICKET_FILE).is_file())
            events = tuple(self._journal.read())
            state = starting_state(
                self._config, message_class=message.message_class, bug_origin=bug_origin,
                has_repro=has_repro, fence=parsed.scope_fence, reopened=False,
                bypass=bool(parsed.gate_bypass), go_binds=go_binds(self._config, events))
        except Exception as e:
            self._report_failure(message, e)
            return None

        intake = Intake(repo=self._repo, git=self._git, journal=self._journal, fs=self._fs)
        try:
            self._fs.write(path, authored.ticket.encode())
            await intake.commit(
                authored.stem, source=f"box:{message.message_class}", state=state)
        except Exception as e:
            try:
                await self._discard(path)
            except Exception as cleanup:
                self._report(
                    f"author: {message.id}: cleanup failed: "
                    f"{type(cleanup).__name__}: {cleanup}")
            self._report_failure(message, e)
            return None
        self._box.resolve(message.id, status="authored", link=authored.stem,
                          note=verdict.summary)
        self._report(f"author: {message.id}: authored as {authored.stem}")
        return authored.stem

    def _record_review(self, message: Message, verdict: RequisitionSnag | RequisitionRMA) -> None:
        triage = dict(message.triage or {})
        triage[REVIEW_CODE] = {
            "verdict": verdict.verdict,
            "summary": verdict.summary,
            "findings": [finding.model_dump(mode="json") for finding in verdict.findings],
        }
        self._box.record_triage(message.id, triage)

    def _report_failure(self, message: Message, error: Exception) -> None:
        self._report(f"author: {message.id}: {type(error).__name__}: {error}; left pending")

    async def _discard(self, path: Path) -> None:
        rel = path.relative_to(self._repo)
        try:
            dirty = next((entry for entry in await self._git.status(self._repo)
                          if entry.path == str(rel)), None)
            if dirty is not None and dirty.code != "??":
                await self._git.restore(self._repo, [rel], source="HEAD")
        except GitError:
            pass
        if path.is_file():
            self._fs.unlink(path)
        if path.parent.is_dir() and not any(path.parent.iterdir()):
            discarded = (self._repo / self._config.state_dir / "spools" / "author"
                         / f"{path.parent.name}.discarded")
            self._fs.replace(path.parent, discarded)

    async def _inputs(self, message: Message, verdict: TriageAuthor, sha: str) -> AuthorInput:
        plan = (self._repo / PLAN_FILE).read_text()
        contract = resolve_plan_sections(plan, (13,))[0][1]
        return AuthorInput(
            produced_by_spec_version="triage", produced_at_sha=sha,
            message_id=message.id, message_class=message.message_class,
            summary=message.summary, detail=message.detail, origin=message.origin,
            triage=verdict, ticket_contract=contract,
            plane=await self._plane(), tree=await self._tree(),
            context_files=self._context_files())

    async def _plane(self) -> str:
        events = tuple(self._journal.read())
        merged = {event.ticket for event in events
                  if event.type == "state_transition" and event.body.get("to") == "merged"
                  and event.ticket}
        rows = []
        for stem in on_disk_stems(self._repo):
            rel = f"{TICKETS_DIR}/{stem}/{TICKET_FILE}"
            try:
                await self._git.rev_parse(self._repo, f"HEAD:{rel}")
            except GitError:
                continue
            text = (self._repo / rel).read_text(errors="replace")
            meta, _ = parse_frontmatter(text)
            suffix = "" if stem in merged else f" [{meta.get('state', 'unknown')}]"
            rows.append(f"{stem}{suffix}: {_goal(text)}")
        return _bounded(rows, AUTHOR_PLANE_CHARS)

    async def _tree(self) -> str:
        tracked = await self._git.ls_files(self._repo)
        return _bounded(tracked, AUTHOR_TREE_CHARS)

    def _context_files(self) -> str:
        parts = []
        for configured in self._config.context_files:
            path = configured if configured.is_absolute() else self._repo / configured
            parts.append(f"### {configured}\n{path.read_text(errors='replace')}")
        return "\n\n".join(parts)


def _goal(text: str) -> str:
    lines = text.splitlines()
    try:
        start = lines.index("## Goal") + 1
    except ValueError:
        return "(no Goal line)"
    return next((line.strip() for line in lines[start:]
                 if line.strip() and not line.startswith("## ")), "(no Goal line)")


def _policy_inputs(message: Message) -> tuple[str | None, bool]:
    """Resolve the closed policy row before a paid authoring call."""
    if message.message_class == "bug_report":
        if message.bug_origin not in ("self_diagnosed", "player"):
            raise ValueError("bug_report bug_origin must be 'self_diagnosed' or 'player'")
        if type(message.has_repro) is not bool:
            raise ValueError("bug_report has_repro must be boolean")
        return message.bug_origin, message.has_repro
    if message.bug_origin is not None or message.has_repro is not None:
        raise ValueError("non-bug message must not carry bug_origin or has_repro")
    return None, False


def _bounded(lines: Sequence[str], limit: int) -> str:
    kept = []
    size = 0
    for line in lines:
        line = _quoted(line)
        added = len(line) + (1 if kept else 0)
        if size + added > limit:
            break
        kept.append(line)
        size += added
    return "\n".join(kept) or "(none)"


def _quoted(text: str) -> str:
    return text.replace(DATA_MARKER, "[squatch-data:")
