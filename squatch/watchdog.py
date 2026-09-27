"""Dormant normalized progress events for the later watchdog detector.

This module deliberately collects observations only. It neither schedules nor
interprets them, so constructing a collector cannot alter a running call.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
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
