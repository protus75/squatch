"""Dormant normalized progress events for the later watchdog detector.

This module deliberately collects observations only. It neither schedules nor
interprets them, so constructing a collector cannot alter a running call.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Literal


WatchdogEventKind = Literal["start", "tool_call"]


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
