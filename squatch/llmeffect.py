"""The LLM call as one journaled effect (SQUATCH_PLAN.md sections 2, 6, 19 Phase 1).

`LLMEffect.call` is the driver's model seam: every call is `Effects.run`
under the attempt-scoped key `llm/<stem>/<run_seq>/<surface>/<attempt>/
<call_seq>` -- intent journaled before the seam is reached, ONE completion
carrying the scrubbed result and its cost after it. A completed key replays
its recorded result and never reaches the LLM seam; a fresh run sequence
(section 6, `run_sequence`) takes fresh keys, so crash recovery is real
work. The result is scrubbed exactly once, here, before it becomes the
completion record and the return value: the executing path and every replay
return the same post-scrub bytes. The stuck budget wraps the seam INSIDE
the effect: on expiry -- or an outer cancellation -- `abort_current` runs
before anything is recorded, so a resistant writer is dead before its
terminal exists and the journal holds intent only.
"""

import asyncio
from dataclasses import asdict

from squatch.effects import Effects, effect, effect_key
from squatch.llm import LLM, LLMRequest, LLMResult
from squatch.redact import Redactor

# The completion's cost field: the metered fields of the result, the ledger's
# read-time fold target (section 6).
COST_FIELDS = ("usd", "input_tokens", "output_tokens", "provider", "model")


def llm_key(stem: str, run_seq: int, surface: str, attempt: int, call_seq: int) -> str:
    return effect_key("llm", stem, run_seq, surface, attempt, call_seq)


class Stuck(Exception):
    """The active call outlived the stuck budget."""


class LLMEffect:
    def __init__(self, *, llm: LLM, effects: Effects, redact: Redactor,
                 stuck_seconds: float | None = None):
        self._llm = llm
        self.effects = effects
        self._redact = redact
        self.stuck_seconds = stuck_seconds

    async def call(self, req: LLMRequest, *, stem: str, run_seq: int, attempt: int,
                   call_seq: int) -> LLMResult:
        return LLMResult(**await self._call(req, stem=stem, run_seq=run_seq,
                                            attempt=attempt, call_seq=call_seq))

    @effect(key=lambda req, *, stem, run_seq, attempt, call_seq:
            llm_key(stem, run_seq, req.surface, attempt, call_seq),
            ticket=lambda req, **_: req.ticket,
            cost=lambda result: {k: result[k] for k in COST_FIELDS})
    async def _call(self, req: LLMRequest, *, stem: str, run_seq: int, attempt: int,
                    call_seq: int) -> dict:
        """The one model call, as JSON data (the completion record IS the
        replayed value)."""
        task = asyncio.ensure_future(self._llm.call(req))
        try:
            done, _ = await asyncio.wait({task}, timeout=self.stuck_seconds)
        except asyncio.CancelledError:
            await self._abort(task)
            raise
        if not done:
            await self._abort(task)
            raise Stuck
        return asdict(_scrubbed(task.result(), self._redact))

    async def _abort(self, task: asyncio.Future) -> None:
        self._llm.abort_current()
        task.cancel()
        await asyncio.wait({task})


def _scrubbed(result: LLMResult, redact: Redactor) -> LLMResult:
    text = redact(result.text)
    return result if text == result.text else LLMResult(
        text=text, input_tokens=result.input_tokens, output_tokens=result.output_tokens,
        provider=result.provider, model=result.model, usd=result.usd)
