"""Governed retrospective runs over one journal window.

The report is deliberately local to this module: it is model-validated by the
ordinary Driver, rendered to Markdown, and committed straight to the reserved
ticket-plane report lane. It is not an OUTBOX or a persisted JSON artifact.
"""

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import Field, field_validator

from squatch.artifacts import Artifact, ClosedModel, StageResult
from squatch.box import Box
from squatch.driver import Driver, LLMStage
from squatch.effects import Effects, effect_key
from squatch.git import Git
from squatch.journal import Event, Journal, render_ts
from squatch.providers import ProviderRuntime
from squatch.redact import Redactor
from squatch.seams import Clock, Filesystem
from squatch.specs import DataBlock, Spec

RETRO_COUNT = 25
RETRO_AGE = timedelta(days=7)
RETRO_SPIKE = 5
RETRO_DIR = Path("tickets/retro")
RETRO_SEQUENCE_WIDTH = 6
ORIGIN_BOUNDARY = "origin"

TRIGGER_COUNT = "merged-tickets"
TRIGGER_AGE = "window-age"
TRIGGER_OVERRIDE = "gate-bypass"
TRIGGER_REWORK = "rework"
TRIGGER_GATE_FAILURE = "gate-failed"
TRIGGER_INTEGRATION_RED = "integration-red"

_RETRO_KEY = re.compile(r"\Aretro/(\d{6})\Z")
_ONE_LINE = "value must be one non-empty line"


class RetroConstructionError(RuntimeError):
    """Production retro was requested without the pipeline's shared Driver."""

    paved_road = ("construct the pipeline through the explicit retro pipeline seam and "
                  "expose its shared Driver as pipeline.stages.driver")


class RetroProposal(ClosedModel):
    fixed_failure: str = Field(min_length=1, max_length=1000)
    overcorrection_risk: str = Field(min_length=1, max_length=1000)
    proposed_spec_paths: tuple[str, ...] = Field(min_length=1)

    @field_validator("fixed_failure", "overcorrection_risk")
    @classmethod
    def _one_line(cls, value: str) -> str:
        value = value.strip()
        if not value or "\n" in value or "\r" in value:
            raise ValueError(_ONE_LINE)
        return value

    @field_validator("proposed_spec_paths")
    @classmethod
    def _spec_paths(cls, paths: tuple[str, ...]) -> tuple[str, ...]:
        if len(paths) != len(set(paths)):
            raise ValueError("proposed_spec_paths must be unique")
        if any(not path.startswith("specs/") or not path.endswith(".md")
               or ".." in Path(path).parts for path in paths):
            raise ValueError("proposed_spec_paths must name specs/*.md files")
        return tuple(sorted(paths))


class RetroArtifact(Artifact):
    """The closed, module-local model output used only to render Markdown."""

    summary: str = Field(min_length=1, max_length=2000)
    observations: tuple[str, ...] = ()
    proposals: tuple[RetroProposal, ...] = ()

    @field_validator("summary")
    @classmethod
    def _summary_line(cls, value: str) -> str:
        value = value.strip()
        if not value or "\n" in value or "\r" in value:
            raise ValueError(_ONE_LINE)
        return value

    @field_validator("observations")
    @classmethod
    def _observation_lines(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        cleaned = tuple(value.strip() for value in values)
        if any(not value or "\n" in value or "\r" in value for value in cleaned):
            raise ValueError(_ONE_LINE)
        return cleaned


class RetroWindow(Artifact):
    """A bounded journal-derived projection consumed by the recurring stage."""

    boundary: str
    started_at: str | None
    ended_at: str
    merged_tickets: tuple[str, ...]
    signal_counts: dict[str, int]
    event_counts: dict[str, int]
    gate_failures: tuple[str, ...]
    spend_usd: float = Field(ge=0)
    tokens: int = Field(ge=0)


def retro_stage(spec: Spec) -> LLMStage:
    def render(window: RetroWindow, findings) -> str:
        return spec.render(
            {"window": DataBlock("engine", window.model_dump_json(indent=2))},
            findings=findings)

    return LLMStage(
        name="retro", surface=spec.surface, spec_version=spec.version,
        tier=spec.tier, effort=spec.effort, consumes=RetroWindow, emits=RetroArtifact,
        gates=(), render=render)


class Window:
    """One stable fold: appending a failure does not change its boundary identity."""

    def __init__(self, events: tuple[Event, ...], now: datetime):
        self.boundary = ORIGIN_BOUNDARY
        self.sequence = 0
        start = 0
        boundary_ts = None
        for index, event in enumerate(events):
            match = _RETRO_KEY.match(event.key or "")
            if event.type == "effect_completion" and match is not None:
                self.boundary = event.key
                self.sequence = int(match.group(1))
                start = index + 1
                boundary_ts = event.ts
        self.events = events[start:]
        self.started_at = boundary_ts or (self.events[0].ts if self.events else None)
        self.now = now
        self.merged = tuple(event.ticket for event in self.events
                            if event.type == "state_transition"
                            and event.body.get("to") == "merged"
                            and event.ticket is not None)
        self.signal_counts = self._signal_counts()

    @property
    def suppressed(self) -> bool:
        return any(event.type == "signal"
                   and event.body.get("kind") == "retro_failed"
                   and event.body.get("window_boundary") == self.boundary
                   for event in self.events)

    @property
    def has_merge(self) -> bool:
        return bool(self.merged)

    def due(self) -> str | None:
        if self.suppressed:
            return None
        if len(self.merged) >= RETRO_COUNT:
            return TRIGGER_COUNT
        if self.started_at is not None:
            started = datetime.fromisoformat(self.started_at)
            if self.now - started >= RETRO_AGE:
                return TRIGGER_AGE
        for kind in (TRIGGER_OVERRIDE, TRIGGER_REWORK, TRIGGER_GATE_FAILURE,
                     TRIGGER_INTEGRATION_RED):
            if self.signal_counts[kind] >= RETRO_SPIKE:
                return kind
        return None

    def projection(self, *, sha: str, spec_version: str) -> RetroWindow:
        event_counts = Counter(event.type for event in self.events)
        gate_failures = tuple(
            event.ticket for event in self.events
            if event.type == "state_transition" and event.body.get("to") == "gate_failed"
            and event.ticket is not None)
        costs = [event.body.get("cost") for event in self.events
                 if event.type == "effect_completion" and isinstance(event.body.get("cost"), dict)]
        return RetroWindow(
            boundary=self.boundary, started_at=self.started_at, ended_at=render_ts(self.now),
            merged_tickets=self.merged, signal_counts=dict(self.signal_counts),
            event_counts=dict(sorted(event_counts.items())), gate_failures=gate_failures,
            spend_usd=sum(float(cost.get("usd") or 0) for cost in costs),
            tokens=sum(int(cost.get("input_tokens") or 0) + int(cost.get("output_tokens") or 0)
                       for cost in costs),
            produced_by_spec_version=spec_version, produced_at_sha=sha)

    def _signal_counts(self) -> Counter[str]:
        counts: Counter[str] = Counter({
            TRIGGER_OVERRIDE: 0, TRIGGER_REWORK: 0, TRIGGER_GATE_FAILURE: 0,
            TRIGGER_INTEGRATION_RED: 0})
        reworks: set[tuple[str, str, str]] = set()
        for event in self.events:
            if event.type == "state_transition" and event.body.get("to") == "gate_failed":
                counts[TRIGGER_GATE_FAILURE] += 1
            if (event.type == "signal" and event.body.get("kind") == "merge_conflict_facts"
                    and event.body.get("integration_red_paths")):
                counts[TRIGGER_INTEGRATION_RED] += 1
            if event.type != "effect_completion":
                continue
            parts = (event.key or "").split("/")
            if len(parts) == 3 and parts[0] == "check":
                result = event.body.get("result")
                invoice = result.get("invoice") if isinstance(result, dict) else None
                checks = invoice.get("checks") if isinstance(invoice, dict) else None
                if isinstance(checks, list) and any(
                        isinstance(check, dict) and check.get("bypassed") is True
                        for check in checks):
                    counts[TRIGGER_OVERRIDE] += 1
            if len(parts) == 6 and parts[0] == "llm" and parts[3] == "rework":
                reworks.add((parts[1], parts[2], parts[4]))
        counts[TRIGGER_REWORK] = len(reworks)
        return counts


class Retro:
    def __init__(self, *, repo: Path, journal: Journal, clock: Clock, fs: Filesystem,
                 git: Git, effects: Effects, box: Box, driver: Driver,
                 providers: ProviderRuntime, spec: Spec, redact: Redactor):
        self._repo = Path(repo)
        self._journal = journal
        self._clock = clock
        self._fs = fs
        self._git = git
        self._effects = effects
        self._box = box
        self._driver = driver
        # Driver already owns the client over this same session payload.
        self.providers = providers
        self._spec = spec
        self._redact = redact

    async def run(self, trigger: str | None = None, *, forced: bool = False) -> bool:
        window = Window(tuple(self._journal.read()), self._clock())
        if window.suppressed:
            self._reconcile_failure_box(window)
            return False
        selected = trigger if forced else window.due()
        if selected is None or (forced and not window.has_merge):
            return False
        try:
            sha = await self._git.rev_parse(self._repo, "HEAD")
            projection = window.projection(sha=sha, spec_version=self._spec.version)
            result: StageResult = await self._driver.run(
                retro_stage(self._spec), projection, ticket=None,
                run_seq=window.sequence + 1, attempt=0, workspace=self._repo, sha=sha)
            if result.outcome != "ok":
                self._failed(window.boundary, selected, result.outcome, result.reason)
                return False
            artifact: RetroArtifact = result.artifact
            await self._commit(window, selected, projection, artifact)
            return True
        except Exception as error:
            self._failed(window.boundary, selected, type(error).__name__, str(error))
            return False

    async def _commit(self, window: Window, trigger: str, projection: RetroWindow,
                      artifact: RetroArtifact) -> None:
        seq = f"{window.sequence + 1:0{RETRO_SEQUENCE_WIDTH}d}"
        rel = RETRO_DIR / f"{seq}.md"
        report = render_report(seq, trigger, projection, artifact).encode()

        async def action() -> dict:
            self._fs.write(self._repo / rel, report)
            await self._git.add(self._repo, [rel.as_posix()])
            sha = await self._git.commit(
                self._repo, f"squatch(retro): {seq}", [rel.as_posix()])
            return {"commit": sha, "path": rel.as_posix()}

        report_key = effect_key("retro", seq)
        await self._effects.run(action, key=report_key, ticket=None)
        for proposal in artifact.proposals:
            identity = proposal_id(
                report_key, proposal.fixed_failure, proposal.overcorrection_risk,
                proposal.proposed_spec_paths)
            detail = json.dumps({
                "retro_report_key": report_key,
                "fixed_failure": proposal.fixed_failure,
                "overcorrection_risk": proposal.overcorrection_risk,
                "proposed_spec_paths": proposal.proposed_spec_paths,
            }, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            self._box.enqueue(
                message_class="retro_finding", summary=proposal.fixed_failure,
                detail=detail, origin=f"retro-proposal/{report_key}/{identity}",
                stage="retro", outcome="ok", retro_report_key=report_key,
                fixed_failure=proposal.fixed_failure,
                overcorrection_risk=proposal.overcorrection_risk,
                proposed_spec_paths=proposal.proposed_spec_paths)

    def _failed(self, boundary: str, trigger: str, error_code: str,
                detail: str | None) -> None:
        identity = f"retro-failed/{boundary}/{trigger}"
        body = {"kind": "retro_failed", "window_boundary": boundary,
                "trigger": trigger, "error_code": error_code}
        if not any(event.type == "signal" and event.key == identity
                   for event in self._journal.read()):
            self._journal.append("signal", body, key=identity)
        self._enqueue_failure(identity, error_code, detail)

    def _reconcile_failure_box(self, window: Window) -> None:
        event = next(
            event for event in window.events
            if event.type == "signal" and event.body.get("kind") == "retro_failed"
            and event.body.get("window_boundary") == window.boundary)
        self._enqueue_failure(
            event.key, event.body.get("error_code", "retro_failed"), None)

    def _enqueue_failure(self, identity: str, error_code: str,
                         detail: str | None) -> None:
        if self._box.by_origin(identity) is not None:
            return
        summary = self._redact(f"retro failed for {identity}: {error_code}")[:240]
        bounded = self._redact(detail or error_code)[:1000]
        self._box.enqueue(
            message_class="failure_report", summary=summary,
            detail=f"{identity}: {bounded}", origin=identity,
            stage="retro", outcome="infra_error")


def proposal_id(retro_report_key: str, fixed_failure: str, overcorrection_risk: str,
                proposed_spec_paths: tuple[str, ...]) -> str:
    """Return the stable compact identity for one report proposal."""
    encoded = json.dumps(
        [retro_report_key, fixed_failure, overcorrection_risk,
         sorted(proposed_spec_paths)],
        ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:16]


def render_report(seq: str, trigger: str, window: RetroWindow,
                  artifact: RetroArtifact) -> str:
    counts = window.signal_counts
    lines = [
        f"# Retro {seq}", "", f"- Trigger: `{trigger}`",
        f"- Window boundary: `{window.boundary}`",
        f"- Window: {window.started_at or 'empty'} through {window.ended_at}", "",
        "## Window projection", "",
        f"- Merged tickets ({len(window.merged_tickets)}): "
        + (", ".join(f"`{stem}`" for stem in window.merged_tickets) or "none"),
        f"- Used gate bypasses: {counts.get(TRIGGER_OVERRIDE, 0)}",
        f"- Rework invocations: {counts.get(TRIGGER_REWORK, 0)}",
        f"- Gate-failed terminals: {counts.get(TRIGGER_GATE_FAILURE, 0)}",
        f"- Integration-red admissions: {counts.get(TRIGGER_INTEGRATION_RED, 0)}",
        f"- Metered spend: ${window.spend_usd:.6f}; tokens: {window.tokens}", "",
        "## Summary", "", artifact.summary, "", "## Observations", "",
    ]
    lines.extend(f"- {item}" for item in artifact.observations)
    if not artifact.observations:
        lines.append("- None.")
    lines.extend(("", "## Proposals", ""))
    for number, proposal in enumerate(artifact.proposals, start=1):
        lines.extend((
            f"### Proposal {number}", "",
            f"- Fixed failure: {proposal.fixed_failure}",
            f"- Overcorrection risk: {proposal.overcorrection_risk}",
            "- Proposed spec paths: "
            + ", ".join(f"`{path}`" for path in proposal.proposed_spec_paths), ""))
    if not artifact.proposals:
        lines.append("No changes proposed.")
    return "\n".join(lines).rstrip() + "\n"
