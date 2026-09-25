"""The one LLM-stage driver (SQUATCH_PLAN.md section 5 invariant 2, section 6).

render spec -> spool the prompt -> call model -> validate artifact schema ->
run gates -> on a schema-invalid artifact or a hard-gate failure feed the
structured findings back and RE-PROMPT the same workspace, bounded by the
retry cap -> terminal. Stages differ only in spec, artifact type, and gate
list. Every captured stream (prompt, response, log line) crosses the
redaction seam before it persists; the rendered prompt is on disk BEFORE
the model is called, so a call that raises or hangs leaves exactly what was
sent. The model seam is the journaled effect in `squatch.llmeffect`: a
completed key replays its recorded result and never reaches the LLM.
"""

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from squatch.artifacts import SUBSTEP_NAMES, STAGE_NAMES, Artifact, Cost, Finding, StageResult
from squatch.caps import RETRY_CAP
from squatch.config import Caps, Severity, Tier
from squatch.enginelog import EngineLog
from squatch.gates import Gate, run_gates
from squatch.llm import WRITING_SURFACES, Effort, LLMRequest, LLMResult
from squatch.llmeffect import LLMEffect, Stuck
from squatch.redact import Redactor
from squatch.seams import Clock, ExecutableNotFound, Filesystem

INVALID_ARTIFACT = "invalid_artifact"
Render = Callable[[Artifact, Sequence[Finding]], str]


@dataclass(frozen=True)
class LLMStage:
    """An LLM stage as the driver sees it: the spec renderer plugs in as
    `render(inputs, findings)`; findings are empty on the first call and the
    structured feedback on every re-prompt."""

    name: str
    surface: str
    spec_version: str
    tier: Tier
    effort: Effort
    consumes: type[Artifact]
    emits: type[Artifact]
    gates: tuple[Gate, ...]
    render: Render

    def __post_init__(self):
        if self.name not in STAGE_NAMES | SUBSTEP_NAMES:
            raise ValueError(f"stage name {self.name!r} is not a StageName or substep name")


class Spool:
    """The attempt-spool writer: `<state_dir>/spools/<stem>/<attempt>/`."""

    def __init__(self, state_dir: Path, *, fs: Filesystem, redact: Redactor):
        self.root = Path(state_dir) / "spools"
        self._fs = fs
        self._redact = redact

    def write(self, stem: str, attempt: int, name: str, text: str) -> Path:
        path = self.root / stem / str(attempt) / name
        self._fs.write(path, self._redact(text).encode())
        return path


class Driver:
    def __init__(self, *, llm: LLMEffect, spool: Spool, log: EngineLog, clock: Clock,
                 retry_cap: int = Caps().retry,
                 severity: Mapping[str, Severity] | None = None):
        self._llm = llm
        self._spool = spool
        self._log = log
        self._clock = clock
        self.retry_cap = retry_cap
        self._severity = severity

    async def run(self, stage: LLMStage, inputs: Artifact, *, ticket: str | None,
                  run_seq: int, attempt: int, workspace: Path, sha: str,
                  terminal_findings: Callable[[Sequence[Finding]], bool] | None = None
                  ) -> StageResult:
        if not isinstance(inputs, stage.consumes):
            raise TypeError(f"{stage.name} consumes {stage.consumes.__name__}, "
                            f"got {type(inputs).__name__}")
        # A ticket-less call (triage, retro, author) spools under its surface.
        stem = ticket if ticket is not None else stage.surface
        provenance = {"produced_by_spec_version": stage.spec_version, "produced_at_sha": sha}
        common = {"stage": stage.name, "surface": stage.surface, "ticket": ticket,
                  "attempt": attempt}
        cost = _CostFold(self._clock)
        findings: tuple[Finding, ...] = ()
        failure = None  # the outcome a re-prompt is clearing
        for call_seq in range(1, self.retry_cap + 2):
            rendered = stage.render(inputs, findings)
            prompt = self._spool.write(stem, attempt, f"{call_seq:03d}-prompt.md", rendered)
            self._log.event("call", call_seq=call_seq, prompt=str(prompt), **common)
            req = LLMRequest(surface=stage.surface, rendered=rendered, tier=stage.tier,
                             effort=stage.effort, ticket=ticket,
                             worktree=workspace if stage.surface in WRITING_SURFACES else None)
            try:
                result = await self._llm.call(req, stem=stem, run_seq=run_seq,
                                              attempt=attempt, call_seq=call_seq)
            except Stuck:
                return self._terminal("timeout", cost.fold(None), (), common,
                                      reason=f"stuck budget of {self._llm.stuck_seconds}s exceeded")
            except ExecutableNotFound:
                # Never a call that RAN: a missing binary is the seam's
                # config/setup refusal (sections 11.1, 15), not an infra terminal
                # that would draw a cap for a defect capability cannot fix.
                raise
            except Exception as e:
                return self._terminal("infra_error", cost.fold(None), (), common,
                                      reason=f"{type(e).__name__}: {e}")
            cost.fold(result)
            self._spool.write(stem, attempt, f"{call_seq:03d}-response.md", result.text)
            self._log.event("response", call_seq=call_seq, provider=result.provider,
                            model=result.model, input_tokens=result.input_tokens,
                            output_tokens=result.output_tokens, usd=result.usd, **common)

            artifact, findings = _parse(stage, result.text, provenance)
            failure = INVALID_ARTIFACT
            if artifact is not None:
                gates = await run_gates(stage.gates, artifact, workspace, severity=self._severity)
                if gates.passed:
                    if gates.soft_failures:
                        self._log.event("soft_findings", call_seq=call_seq,
                                        findings=_dump(gates.soft_failures), **common)
                    return self._terminal("ok", cost.final(), gates.soft_failures, common,
                                          artifact=artifact)
                findings, failure = gates.hard_failures, "gate_failed"
                if terminal_findings is not None and terminal_findings(findings):
                    return self._terminal(failure, cost.final(), findings, common)
            if call_seq <= self.retry_cap:
                self._log.event("reprompt", call_seq=call_seq, reason=failure,
                                findings=_dump(findings), **common)
        return self._terminal(failure, cost.final(), findings, common,
                              reason="retry cap spent", cap=RETRY_CAP)


    def _terminal(self, outcome, cost, findings, common, *, artifact=None, **detail):
        self._log.event("terminal", outcome=outcome, attempts=cost.attempts,
                        usd=cost.usd, **detail, **common)
        return StageResult(outcome=outcome, artifact=artifact, findings=list(findings), cost=cost,
                           reason=detail.get("reason"))


class _CostFold:
    def __init__(self, clock: Clock):
        self._clock = clock
        self._started = clock()
        self.attempts = 0
        self.tokens = 0
        self.usd = 0.0
        self.provider = None
        self.model = None

    def fold(self, result: LLMResult | None) -> Cost:
        self.attempts += 1
        if result is not None:
            # Unreported usage counts as zero tokens; the usd field still
            # carries the cli est_cost fallback.
            self.tokens += (result.input_tokens or 0) + (result.output_tokens or 0)
            self.usd += result.usd
            self.provider, self.model = result.provider, result.model
        return self.final()

    def final(self) -> Cost:
        seconds = (self._clock() - self._started).total_seconds()
        return Cost(tokens=self.tokens, seconds=seconds, attempts=self.attempts,
                    usd=self.usd, provider=self.provider, model=self.model)



def _parse(stage: LLMStage, text: str, provenance: dict
           ) -> tuple[Artifact | None, tuple[Finding, ...]]:
    """The model emits the artifact as one JSON object; the driver stamps
    provenance (invariant 1) and validates. Any defect is a finding fed back."""
    road = f"emit exactly one JSON object with the fields of {stage.emits.__name__}"
    try:
        data = json.loads(text)
    except ValueError as e:
        return None, (_finding(f"output is not JSON: {e}", road),)
    if not isinstance(data, dict):
        return None, (_finding(f"output is a JSON {type(data).__name__}, not an object", road),)
    try:
        return stage.emits.model_validate({**data, **provenance}), ()
    except ValidationError as e:
        return None, tuple(
            _finding(f"{'.'.join(str(p) for p in err['loc']) or '<root>'}: {err['msg']}", road)
            for err in e.errors())


def _finding(message: str, road: str) -> Finding:
    return Finding(code=INVALID_ARTIFACT, message=message, paved_road=road)


def _dump(findings: Sequence[Finding]) -> list[dict]:
    return [f.model_dump() for f in findings]
