"""Normalized progress accounting and the Stages-owned production observer."""

import asyncio
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Literal

from squatch.git import Git, GitError
from squatch.llm import LLMRequest, LLMResult
from squatch.seams import Clock, ExecutableNotFound, Sleep

if TYPE_CHECKING:
    from squatch.journal import Journal
    from squatch.providers import CliClient, ProviderRuntime
    from squatch.tickets import Ticket


WatchdogEventKind = Literal["start", "tool_call"]
OBSERVE_SECONDS = 10.0


@dataclass(frozen=True)
class WatchdogEvent:
    """One provider-normalized observation relevant to progress accounting."""

    provider: Literal["claude", "codex"]
    kind: WatchdogEventKind
    input_tokens: int | None = None
    output_tokens: int | None = None
    usd: float | None = None


WatchdogCallback = Callable[[WatchdogEvent], None]


@dataclass
class EventCollector:
    """An injectable callback that retains events in arrival order for a caller."""

    events: list[WatchdogEvent] = field(default_factory=list)

    def __call__(self, event: WatchdogEvent) -> None:
        self.events.append(event)


WatchdogRegion = Literal["healthy", "soft", "stuck"]
WatchdogDecisionKind = Literal["soft_trip", "hard_timeout"]


@dataclass(frozen=True)
class WatchdogAssessment:
    """The detector's local assessment; callers decide what acts on it."""

    region: WatchdogRegion
    decision: WatchdogDecisionKind | None
    elapsed: float
    spend_usd: float


def _relative_parts(path: str | PurePosixPath) -> tuple[str, ...] | None:
    """Return a path's safe relative components, refusing ambiguous input."""
    text = path.as_posix() if isinstance(path, PurePosixPath) else str(path)
    candidate = PurePosixPath(text)
    if candidate.is_absolute() or any(part in {".", ".."} for part in text.split("/")):
        return None
    return candidate.parts


class WatchdogDetector:
    """Deterministically account for a call's progress-free time and spend.

    This construction seam has no callback or process dependency, so an
    assessment cannot notify or abort a running call.
    """

    def __init__(
            self, *, clock: Callable[[], float], expected: float, stuck: float,
            scope_fence: Sequence[str | PurePosixPath], cost_basis_usd: float,
            provider_reports_metered_usage: Mapping[str, bool],
            flat_usd_estimates: Mapping[str, float]):
        self._clock = clock
        self._expected = expected
        self._stuck = stuck
        self._scope_fence = tuple(
            parts for prefix in scope_fence if (parts := _relative_parts(prefix)) is not None)
        self._cost_basis_usd = cost_basis_usd
        self._provider_reports_metered_usage = provider_reports_metered_usage
        self._flat_usd_estimates = flat_usd_estimates
        self._started_at = clock()
        self._cap_wait_elapsed = 0.0
        self._spend_usd = 0.0
        self._soft_trips: set[tuple[str, int]] = set()
        self.events: list[WatchdogEvent] = []
        self.input_tokens = 0
        self.output_tokens = 0

    def observe_event(self, event: WatchdogEvent) -> None:
        """Retain an event and account for its reported or declared USD cost."""
        self.events.append(event)
        self.input_tokens += event.input_tokens or 0
        self.output_tokens += event.output_tokens or 0
        if self._provider_reports_metered_usage[event.provider]:
            self._spend_usd += event.usd or 0.0
        elif event.kind == "start":
            self._spend_usd += (
                event.usd if event.usd is not None else self._flat_usd_estimates[event.provider])

    def observe_mutation(self, path: str | PurePosixPath) -> bool:
        """Reset spend only for a safe declared output beneath the scope fence."""
        path_parts = _relative_parts(path)
        if (path_parts is None
                or not any(path_parts[:len(prefix)] == prefix for prefix in self._scope_fence)):
            return False
        self._spend_usd = 0.0
        return True

    def observe_cap_wait(self, elapsed: float) -> None:
        """Record provider-cap time, which is outside progress-time accounting."""
        self._cap_wait_elapsed += elapsed

    def assess(self, *, ticket: str, run_seq: int) -> WatchdogAssessment:
        """Classify the current region and emit at most one soft decision per run."""
        elapsed = self._clock() - self._started_at - self._cap_wait_elapsed
        if elapsed >= self._stuck:
            return WatchdogAssessment("stuck", "hard_timeout", elapsed, self._spend_usd)
        if elapsed >= self._expected * 1.5:
            key = (ticket, run_seq)
            if self._spend_usd > 3 * self._cost_basis_usd and key not in self._soft_trips:
                self._soft_trips.add(key)
                return WatchdogAssessment("soft", "soft_trip", elapsed, self._spend_usd)
            return WatchdogAssessment("soft", None, elapsed, self._spend_usd)
        return WatchdogAssessment("healthy", None, elapsed, self._spend_usd)


class WatchdogLLM:
    """Bind run identity around CliClient without changing the generic LLM seam."""

    kind: Literal["api", "cli"] = "cli"

    def __init__(self, client: "CliClient", *, registry: "ProviderRuntime", journal: "Journal",
                 clock: Clock, git: Git, sleep: Sleep = asyncio.sleep):
        self.client = client
        self._registry = registry
        self._journal = journal
        self._clock = clock
        self._git = git
        self._sleep = sleep
        self.clear()

    def bind(self, ticket: "Ticket", run_seq: int) -> None:
        self.clear()
        self._ticket = ticket
        self._run_seq = run_seq
        self._started = self._clock().timestamp()

    def clear(self) -> None:
        self._ticket = None
        self._detector = None
        self._worktree = None
        self._snapshot = {}
        self._head = None
        self._inflight = False
        self._basis = {}

    def observe_mutation(self, path: str) -> None:
        if self._detector is not None:
            self._detector.observe_mutation(path)

    def observe_cap_wait(self, elapsed: float) -> None:
        if self._detector is not None:
            self._detector.observe_cap_wait(elapsed)

    async def _sample(self) -> None:
        if self._worktree is None:
            return
        try:
            head = await self._git.rev_parse(self._worktree, "HEAD")
            status = await self._git.status(self._worktree)
            current = {path: entry.code for entry in status if entry.code != "??"
                       for path in entry.path.split(" -> ")}
            if any(entry.code == "??" for entry in status):
                current.update((path, "??") for path in
                               await self._git.untracked_names(self._worktree))
            changed = {path for path in current.keys() | self._snapshot.keys()
                       if current.get(path) != self._snapshot.get(path)}
            if self._head is not None and head != self._head:
                changed.update(await self._git.diff_names(self._worktree, self._head, head))
        except (GitError, OSError, ExecutableNotFound, TimeoutError):
            # Observation must not replace a provider failure or cancellation.
            return
        if self._head is not None:
            for path in changed:
                self.observe_mutation(path)
        self._snapshot = current
        self._head = head

    def _signal(self, spiral: Literal["spend_without_progress", "stuck"]) -> None:
        from squatch.effects import effect_key

        stem, seq = self._ticket.stem, self._run_seq
        key = effect_key("watchdog", stem, spiral, seq)
        if not any(e.type == "signal" and e.key == key for e in self._journal.read()):
            self._journal.append("signal", {
                "kind": "watchdog", "ticket": stem, "spiral": spiral, "run_seq": seq},
                ticket=stem, key=key)

    def _assess(self) -> None:
        if self._detector is None:
            return
        assessment = self._detector.assess(
            ticket=self._ticket.stem, run_seq=self._run_seq)
        if assessment.decision == "soft_trip":
            self._signal("spend_without_progress")
        # Hard termination belongs exclusively to LLMEffect's abort/unwind.

    async def _observe(self) -> None:
        while True:
            await self._sleep(OBSERVE_SECONDS)
            await self._sample()
            self._assess()

    async def call(self, req: LLMRequest) -> LLMResult:
        from squatch.providers import ADAPTERS

        if self._ticket is None:
            return await self.client.call(req)
        resolved = self._registry.resolve(req.tier, req.surface)
        row = resolved.provider
        served = row.name, resolved.model
        metered = ADAPTERS[row.name].reports_cost
        basis = self._basis.get(served, row.limits.est_cost_per_call_usd)
        if self._detector is None:
            self._detector = WatchdogDetector(
                clock=lambda: self._clock().timestamp(),
                expected=self._ticket.expected_minutes * 60,
                stuck=self._ticket.stuck_minutes * 60,
                scope_fence=self._ticket.scope_fence, cost_basis_usd=basis or 0,
                provider_reports_metered_usage={name: a.reports_cost
                                               for name, a in ADAPTERS.items()},
                flat_usd_estimates={row.name: row.limits.est_cost_per_call_usd})
            self._detector._started_at = self._started
        # A metered row's last actual call is its basis; until it reports a
        # price, no soft assessment can infer one from token counts.
        self._detector._cost_basis_usd = basis if basis is not None else float("inf")
        stream_usd = 0.0

        def on_event(event):
            nonlocal stream_usd
            stream_usd += event.usd or 0.0
            self._detector.observe_event(event)
            self._assess()

        # Stages has no provider-cap wait in its call path yet. The detector
        # therefore receives no wait observations; thresh owns future admission.
        self._inflight = True
        observer = None
        try:
            if req.worktree is not None and req.worktree != self._worktree:
                self._worktree = req.worktree
                await self._sample()
            observer = asyncio.create_task(self._observe())
            result = await self.client.call_resolved(req, resolved, on_event=on_event)
            if metered:
                self._basis[served] = result.usd
                self._detector._cost_basis_usd = result.usd
                if not stream_usd:
                    self._detector.observe_event(WatchdogEvent(
                        row.name, "tool_call", usd=result.usd))
        finally:
            if observer is not None:
                observer.cancel()
                await asyncio.gather(observer, return_exceptions=True)
            # Git observes commits as well as dirty paths without reading a
            # directory fence's contents on the synchronous stream callback.
            try:
                await self._sample()
            finally:
                self._inflight = False
        self._assess()
        return result

    def abort_current(self) -> None:
        try:
            # LLMEffect owns the deadline. Its abort runs either on timeout or
            # in the cancelled Driver task; only the former is a stuck signal.
            # Rechecking elapsed here loses timeouts to task-start/timer skew.
            caller = asyncio.current_task()
            if (self._ticket is not None and self._inflight
                    and caller is not None and not caller.cancelling()):
                self._signal("stuck")
        finally:
            self.client.abort_current()
