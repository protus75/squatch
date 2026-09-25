"""Deterministic Reject-queue routing and its journal-derived projection."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from squatch.caps import spent
from squatch.config import Config
from squatch.diagnose import DiagnosisRecord
from squatch.journal import Event

MARKER = "reject_queue"
ARRIVAL = "reject_queue_arrival"


@dataclass(frozen=True)
class Routing:
    routed: str | None
    reason: str | None


@dataclass(frozen=True)
class Arrival:
    reason: str
    ts: str
    run_seq: int | None


def route(config: Config, events: Iterable[Event], stem: str, outcome: str,
          record: DiagnosisRecord) -> Routing:
    """Route one diagnosed terminal after all of that recovery's cap draws."""
    del outcome
    reason = spent(config, events, stem)
    if reason is not None:
        return Routing(MARKER, reason)
    if record.call == "skipped":
        return Routing(None, None)
    if record.verdict is None:
        return Routing(MARKER, "no schema-valid diagnosis verdict")
    if record.verdict in {"reject", "abandon-human", "split"}:
        return Routing(MARKER, f"diagnosis verdict {record.verdict}")
    return Routing(None, None)


def awaiting(events: Iterable[Event]) -> Mapping[str, Arrival]:
    """Fold unresolved Reject arrivals, with either actor's verdict releasing them."""
    result: dict[str, Arrival] = {}
    for event in events:
        stem = event.ticket
        if stem is None:
            continue
        if event.type == "state_transition":
            result.pop(stem, None)
            if event.body.get("routed") == MARKER:
                result[stem] = Arrival(
                    reason=str(event.body.get("reject_reason", "Reject queue arrival")),
                    ts=event.ts, run_seq=event.body.get("run_seq"))
        elif (event.type == "signal" and event.body.get("kind") == "escalation"
              and event.body.get("escalation") == ARRIVAL):
            result[stem] = Arrival(
                reason=str(event.body.get("reason", "Reject queue arrival")),
                ts=event.ts, run_seq=event.body.get("run_seq"))
        elif (event.type == "signal"
              and event.body.get("kind") in {"confirm", "reject"}):
            result.pop(stem, None)
    return result
