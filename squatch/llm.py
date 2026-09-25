"""The LLM interface: the one seam every model call crosses (SQUATCH_PLAN.md section 6).

The request/result shapes are a kernel contract the driver and cost capture
both call. Phase 0 ships the scripted fake; the `cli` implementation is the
Phase 1 provider layer, and `api` is a D10 return.
"""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from squatch.config import Tier

# The LLM stage names plus `diagnose` and the engine review surface
# `requisition_review` (section 5 invariant 6); host review surfaces extend
# this at config load.
LLM_SURFACES: frozenset[str] = frozenset({
    "author", "implement", "review", "rework", "triage", "retro",
    "diagnose", "requisition_review",
})
# The closed allowlist of tree-writing surfaces (section 6): Implement is the
# one surface that mutates the tree; every other surface runs read-only.
WRITING_SURFACES: frozenset[str] = frozenset({"implement"})

Effort = Literal["low", "medium", "high", "max"]
TIERS: frozenset[str] = frozenset(Tier.__args__)
EFFORTS: frozenset[str] = frozenset(Effort.__args__)


@dataclass(frozen=True)
class LLMRequest:
    surface: str
    rendered: str
    tier: Tier
    effort: Effort
    ticket: str | None
    worktree: Path | None

    def __post_init__(self):
        if self.surface not in LLM_SURFACES:
            raise ValueError(f"surface {self.surface!r} is not an llm_surface")
        if self.tier not in TIERS:
            raise ValueError(f"tier {self.tier!r} is not an agent tier")
        if self.effort not in EFFORTS:
            raise ValueError(f"effort {self.effort!r} is not an agent effort")


@dataclass(frozen=True)
class LLMResult:
    text: str
    input_tokens: int | None  # None when a cli stream reports no usage
    output_tokens: int | None
    provider: str
    model: str
    usd: float


class LLM(Protocol):
    kind: Literal["api", "cli"]

    async def call(self, req: LLMRequest) -> LLMResult: ...

    def abort_current(self) -> None:
        """Synchronous kill seam: returns only once the external writer can
        no longer mutate the worktree. Never behind @effect."""
        ...


@dataclass(frozen=True)
class Hang:
    """A scripted call that never returns on its own. `resist=True` ignores
    cancellation and yields only to `abort_current`, like a CLI subprocess
    that outlives a dropped await."""

    resist: bool = False


Scripted = str | LLMResult | BaseException | Hang


class FakeLLM:
    """Returns scripted responses in order and records every request."""

    kind: Literal["api", "cli"] = "cli"

    def __init__(self, *script: Scripted, provider: str = "fake", model: str = "fake-1"):
        self._script = list(script)
        self.provider = provider
        self.model = model
        self.requests: list[LLMRequest] = []
        self.aborted = 0
        self._release = asyncio.Event()

    async def call(self, req: LLMRequest) -> LLMResult:
        self.requests.append(req)
        if not self._script:
            raise AssertionError("fake LLM script exhausted")
        item = self._script.pop(0)
        if isinstance(item, BaseException):
            raise item
        if isinstance(item, Hang):
            await self._hang(item)
            raise asyncio.CancelledError
        if isinstance(item, str):
            return LLMResult(text=item, input_tokens=None, output_tokens=None,
                             provider=self.provider, model=self.model, usd=0.0)
        return item

    async def _hang(self, hang: Hang) -> None:
        self._release.clear()
        while True:
            try:
                await self._release.wait()
                return
            except asyncio.CancelledError:
                if not hang.resist:
                    raise

    def abort_current(self) -> None:
        self.aborted += 1
        self._release.set()
