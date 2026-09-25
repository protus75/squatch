"""The bootstrap Suggestion Box's one-pass sequential consumer."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

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
from squatch.redact import Redactor
from squatch.registry import Record, commit as commit_record, load as load_records, write
from squatch.seams import Clock, Filesystem
from squatch.specs import DATA_MARKER, DataBlock, Spec, load_spec
from squatch.tickets import KINDS, PRIORITIES, TICKETS_DIR, on_disk_stems, parse_frontmatter

TRIAGE_CONTEXT_CHARS = 20000
TRIAGE_STUCK_SECONDS = 600
TRIAGE_RETRY_CAP = 1


class TriageInput(Artifact):
    message_id: str
    message_class: str
    summary: str
    detail: str
    origin: str
    open_work: str
    merged_work: str
    decisions: str


class TriageAuthor(Artifact):
    verdict: Literal["author"]
    summary: str = Field(min_length=1)
    kind: str
    priority: str
    goal: str = Field(min_length=1)
    why: str = Field(min_length=1)

    @model_validator(mode="after")
    def _closed_vocabularies(self):
        if self.kind not in KINDS:
            raise ValueError(f"kind must be one of {sorted(KINDS)}")
        if self.priority not in PRIORITIES:
            raise ValueError(f"priority must be one of {sorted(PRIORITIES)}")
        return self


class TriageTombstone(Artifact):
    verdict: Literal["tombstone"]
    link: str = Field(min_length=1)
    reopen_after_days: int = Field(ge=1)
    rationale: str = Field(min_length=1)


class TriageDecision(Artifact):
    verdict: Literal["decision"]
    reopen_after_days: int = Field(ge=1)
    rationale: str = Field(min_length=1)
    evidence: str = Field(min_length=1)


TRIAGE_EMITS: Mapping[str, type[Artifact]] = {
    "author": TriageAuthor, "tombstone": TriageTombstone, "decision": TriageDecision}


class _TriageReply(Artifact):
    """Driver-facing union; the consumer converts it to its concrete branch."""

    verdict: str
    summary: str | None = None
    kind: str | None = None
    priority: str | None = None
    goal: str | None = None
    why: str | None = None
    link: str | None = None
    reopen_after_days: int | None = None
    rationale: str | None = None
    evidence: str | None = None

    @model_validator(mode="after")
    def _branch_shape(self):
        model = TRIAGE_EMITS.get(self.verdict)
        if model is None:
            raise ValueError(f"verdict must be one of {sorted(TRIAGE_EMITS)}")
        common = {"artifact_schema_version", "produced_by_spec_version", "produced_at_sha",
                  "verdict"}
        wanted = common | set(model.model_fields)
        supplied = common | {name for name in self.model_fields_set
                             if getattr(self, name, None) is not None}
        if supplied != wanted:
            raise ValueError(f"{self.verdict} verdict fields must be exactly "
                             f"{sorted(wanted - common)}")
        model.model_validate(self.model_dump(include=wanted))
        return self

    def concrete(self) -> Artifact:
        model = TRIAGE_EMITS[self.verdict]
        return model.model_validate(self.model_dump(include=set(model.model_fields)))


@dataclass(frozen=True)
class TriageStage(LLMStage):
    emits_by_verdict: Mapping[str, type[Artifact]]


def triage_stage(spec: Spec, *, allowed_links: frozenset[str] = frozenset()) -> TriageStage:
    """Build Triage's branch stage, including the projection-bound link check."""
    if spec.emits != {name: model.__name__ for name, model in TRIAGE_EMITS.items()}:
        raise ValueError("triage spec emits do not match the triage verdict artifacts")

    class Reply(_TriageReply):
        @model_validator(mode="after")
        def _link_is_rendered(self):
            if self.verdict == "tombstone" and self.link not in allowed_links:
                raise ValueError("tombstone link must be an id or stem in the rendered projections")
            return self

    Reply.__name__ = "TriageReply"

    def render(inputs: TriageInput, findings: Sequence) -> str:
        message = (f"id: {inputs.message_id}\nmessage_class: {inputs.message_class}\n"
                   f"summary: {inputs.summary}\ndetail: {inputs.detail}\norigin: {inputs.origin}\n")
        return spec.render({
            "message": DataBlock("untrusted", _quoted(message)),
            "open_work": DataBlock("engine", inputs.open_work),
            "merged_work": DataBlock("engine", inputs.merged_work),
            "decisions": DataBlock("engine", inputs.decisions),
        }, findings=findings)

    return TriageStage(
        name="triage", surface=spec.surface, spec_version=spec.version,
        tier=spec.tier, effort=spec.effort, consumes=TriageInput, emits=Reply,
        gates=(), render=render, emits_by_verdict=TRIAGE_EMITS)


class _PassSpool:
    """Keep every message's driver files distinct inside one pass directory."""

    def __init__(self, spool: Spool, pass_number: int):
        self._spool = spool
        self._pass = pass_number
        self.message_id = "message"

    def write(self, stem: str, attempt: int, name: str, text: str) -> Path:
        return self._spool.write(stem, self._pass, f"{self.message_id}-{name}", text)


class Triage:
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

    async def run(self, spec: Spec) -> None:
        # Local import avoids making the artifact type shared by these two
        # stages into a module-import cycle.
        from squatch.author import Author

        messages = self._box.pending()
        pass_number = sum(1 for event in self._journal.read()
                          if event.type == "signal"
                          and event.body.get("kind") == "triage_pass")
        if not messages:
            self._report("triage: nothing pending")
        triaged = {name: [] for name in (*TRIAGE_EMITS, "authored")}
        skipped: list[str] = []
        sha = await self._git.rev_parse(self._repo, "HEAD")
        effect = LLMEffect(llm=self._llm, effects=Effects(self._journal), redact=self._redact,
                           stuck_seconds=TRIAGE_STUCK_SECONDS)
        pass_spool = _PassSpool(
            Spool(self._repo / self._config.state_dir, fs=self._fs, redact=self._redact),
            pass_number)
        driver = Driver(llm=effect, spool=pass_spool, log=self._log, clock=self._clock,
                        retry_cap=TRIAGE_RETRY_CAP)
        author = Author(
            repo=self._repo, config=self._config, git=self._git, fs=self._fs,
            clock=self._clock, journal=self._journal, llm=self._llm, log=self._log,
            redact=self._redact, report=self._report)
        author_spec = load_spec(Path(spec.source).with_name("author.md"))
        for message in messages:
            if isinstance(message.triage, dict) and message.triage.get("verdict") == "author":
                verdict = TriageAuthor.model_validate(message.triage)
                stem = await author.run(author_spec, message, verdict,
                                        pass_number=pass_number,
                                        sha=await self._git.rev_parse(self._repo, "HEAD"))
                if stem is not None:
                    triaged["authored"].append(stem)
                else:
                    skipped.append(message.id)
                continue
            inputs, links = await self._inputs(message, sha)
            pass_spool.message_id = message.id
            result = await driver.run(
                triage_stage(spec, allowed_links=links), inputs, ticket=None,
                run_seq=message.seq, attempt=pass_number, workspace=self._repo, sha=sha)
            if result.outcome != "ok" or not isinstance(result.artifact, _TriageReply):
                skipped.append(message.id)
                self._report(f"triage: {message.id}: {result.outcome}; left pending")
                continue
            verdict = result.artifact.concrete()
            triaged[verdict.verdict].append(message.id)
            if isinstance(verdict, TriageAuthor):
                self._box.record_triage(message.id, verdict.model_dump(mode="json"))
                stem = await author.run(author_spec, message, verdict,
                                        pass_number=pass_number,
                                        sha=await self._git.rev_parse(self._repo, "HEAD"))
                if stem is not None:
                    triaged["authored"].append(stem)
                else:
                    skipped.append(message.id)
                continue
            await self._apply(message, verdict)
        self._journal.append("signal", {"kind": "triage_pass", "pass": pass_number,
                                        "triaged": triaged, "skipped": skipped})

    async def _inputs(self, message: Message, sha: str) -> tuple[TriageInput, frozenset[str]]:
        events = tuple(self._journal.read())
        merged = {event.ticket for event in events
                  if event.type == "state_transition" and event.body.get("to") == "merged"
                  and event.ticket}
        recency = {event.ticket: index for index, event in enumerate(events)
                   if event.type == "signal" and event.body.get("kind") == "ticket_intake"
                   and event.ticket}
        open_rows: list[tuple[str, str]] = []
        merged_rows: list[tuple[str, str]] = []
        stems = sorted(on_disk_stems(self._repo),
                       key=lambda stem: (recency.get(stem, -1), stem), reverse=True)
        for stem in stems:
            rel = f"{TICKETS_DIR}/{stem}/ticket.md"
            try:
                await self._git.rev_parse(self._repo, f"HEAD:{rel}")
            except GitError:
                continue
            text = (self._repo / rel).read_text(errors="replace")
            meta, _ = parse_frontmatter(text)
            goal = _goal(text)
            if stem in merged:
                merged_rows.append((stem, f"{stem}: {goal}"))
            else:
                open_rows.append((stem, f"{stem} [{meta.get('state', 'unknown')}]: {goal}"))
        records = sorted(load_records(self._repo),
                         key=lambda record: int(record.message.split("-", 2)[1]), reverse=True)
        decisions = [(record.id, f"{record.id} [{record.kind}] -> {record.link}: "
                      f"{record.body.splitlines()[0]}") for record in records]
        open_text, open_links = _render_projection(open_rows)
        merged_text, merged_links = _render_projection(merged_rows)
        decision_text, decision_links = _render_projection(decisions)
        links = open_links | merged_links | decision_links
        return TriageInput(
            produced_by_spec_version="box", produced_at_sha=sha,
            message_id=message.id, message_class=message.message_class,
            summary=message.summary, detail=message.detail, origin=message.origin,
            open_work=open_text, merged_work=merged_text, decisions=decision_text), links

    async def _apply(self, message: Message, verdict: Artifact) -> None:
        record_id = f"{verdict.verdict}-{message.seq:06d}"
        if isinstance(verdict, TriageTombstone):
            record = Record(id=record_id, kind="tombstone", link=verdict.link,
                            reopen_after_days=verdict.reopen_after_days, message=message.id,
                            body=verdict.rationale)
            status = "tombstoned"
        elif isinstance(verdict, TriageDecision):
            record = Record(id=record_id, kind="decision", link=message.id,
                            reopen_after_days=verdict.reopen_after_days, message=message.id,
                            body=f"{verdict.rationale}\n\nEvidence: {verdict.evidence}")
            status = "decided"
        else:
            raise TypeError(f"unknown triage artifact {type(verdict).__name__}")
        rel = f"tickets/decisions/{record.id}.md"
        try:
            await self._git.rev_parse(self._repo, f"HEAD:{rel}")
        except GitError:
            write(self._repo, record, fs=self._fs)
            await commit_record(self._repo, record, git=self._git)
        else:
            committed = next((item for item in load_records(self._repo)
                              if item.id == record.id), None)
            if committed != record:
                raise ValueError(f"committed registry record {record.id} conflicts with "
                                 f"triage verdict for {message.id}")
        self._box.resolve(message.id, status=status, link=record.id, note=record.body)
        self._report(f"triage: {message.id}: {status} as {record.id}")


def _goal(text: str) -> str:
    lines = text.splitlines()
    try:
        start = lines.index("## Goal") + 1
    except ValueError:
        return "(no Goal line)"
    return next((line.strip() for line in lines[start:]
                 if line.strip() and not line.startswith("## ")), "(no Goal line)")


def _projection(rows: list[tuple[str, str]]) -> str:
    return _render_projection(rows)[0]


def _render_projection(rows: list[tuple[str, str]]) -> tuple[str, frozenset[str]]:
    kept: list[str] = []
    visible: set[str] = set()
    size = 0
    for id, line in rows:
        line = _quoted(line)
        added = len(line) + (1 if kept else 0)
        if size + added > TRIAGE_CONTEXT_CHARS:
            break
        kept.append(line)
        visible.add(id)
        size += added
    return ("\n".join(kept) or "(none)"), frozenset(visible)


def _quoted(text: str) -> str:
    """Quote the engine delimiter only in its model-visible representation."""
    return text.replace(DATA_MARKER, "[squatch-data:")
