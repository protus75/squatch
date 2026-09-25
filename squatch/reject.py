"""Deterministic Reject-queue routing and its journal-derived projection."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from squatch.caps import spent
from squatch.config import Config
from squatch.diagnose import DiagnosisRecord
from squatch.journal import Event
from squatch.ladder import Rung, identical, next_rung, oscillating, same_wall
from squatch.providers import Registry

MARKER = "reject_queue"
ARRIVAL = "reject_queue_arrival"


@dataclass(frozen=True)
class Routing:
    routed: str | None
    reason: str | None
    rung: Rung | None = None


@dataclass(frozen=True)
class Arrival:
    reason: str
    ts: str
    run_seq: int | None


def route(config: Config, events: Iterable[Event], stem: str, outcome: str,
          record: DiagnosisRecord, *, current: Rung | None = None, delivery=None) -> Routing:
    """Route one diagnosed terminal after all of that recovery's cap draws."""
    events = tuple(events)
    reason = spent(config, events, stem)
    if reason is not None:
        return Routing(MARKER, reason)
    if record.call == "skipped":
        return Routing(None, None)
    if record.verdict is None:
        return Routing(MARKER, "no schema-valid diagnosis verdict")
    current_codes = (() if delivery is None else
                     tuple(sorted({finding.code for finding in delivery.findings})))
    current_reason = ",".join(current_codes) if current_codes else outcome
    prospective = (*events, Event(v=1, type="state_transition", ts="", ticket=stem,
                                  key=None, body={"to": outcome, "reason": current_reason,
                                                  "finding_codes": list(current_codes)}))
    trigger = None
    if oscillating(prospective, stem):
        trigger = "oscillating finding codes"
    elif identical(prospective, stem):
        trigger = "identical terminal reasons"
    elif record.verdict == "escalate":
        trigger = "diagnosis verdict escalate"
    elif (record.verdict == "retry" and delivery is not None
          and same_wall(events, stem, delivery)):
        trigger = "retry returned to the same gate wall"
    if trigger is not None:
        if current is None:
            current = Rung(config.routing_default_tier, "medium")
        rung = next_rung(Registry(config), current)
        if rung is not None:
            return Routing("ladder", trigger, rung)
        return Routing(MARKER, f"{trigger}; capability ladder exhausted")
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
