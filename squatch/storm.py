"""Dormant, journal-backed storm occurrence window."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from squatch.journal import Event, Journal, JournalCorruption, render_ts


THRESHOLD = 5
WINDOW = timedelta(hours=1)
_KIND = "storm_occurrence"
_KEY_PREFIX = "storm-occurrence"


@dataclass(frozen=True)
class OccurrenceWindow:
    """One signature's ordered, still-live occurrence identities."""

    occurrence_ids: tuple[str, ...]
    count: int
    over_threshold: bool


def fold(events: Iterable[Event], *, now: datetime) -> dict[str, OccurrenceWindow]:
    """Project the complete journal into its half-open storm windows."""
    render_ts(now)
    lower = now - WINDOW
    occurrences: dict[str, list[str]] = {}
    for event in events:
        if event.type != "signal" or event.body.get("kind") != _KIND:
            continue
        signature, occurrence_id, emitting_stage = _occurrence(event)
        occurred_at = datetime.fromisoformat(event.ts)
        if lower < occurred_at <= now:
            occurrences.setdefault(signature, []).append(occurrence_id)
    return {
        signature: OccurrenceWindow(tuple(ids), len(ids), len(ids) > THRESHOLD)
        for signature, ids in occurrences.items()
    }


class StormLedger:
    """Record producer-supplied occurrence identities and read their window."""

    def __init__(self, *, journal: Journal) -> None:
        self._journal = journal

    def record(self, *, signature: str, occurrence_id: str,
               emitting_stage: str | None = None) -> bool:
        """Append an occurrence once, returning whether this call wrote it."""
        _validate_identity(signature, occurrence_id, emitting_stage)
        key = f"{_KEY_PREFIX}/{signature}/{occurrence_id}"
        events = tuple(self._journal.read())
        existing = [event for event in events if event.type == "signal" and event.key == key]
        if existing:
            for event in existing:
                _occurrence(event)
            return False
        self._journal.append("signal", {
            "kind": _KIND,
            "signature": signature,
            "occurrence_id": occurrence_id,
            "emitting_stage": emitting_stage,
        }, key=key)
        return True

    def window(self, *, now: datetime) -> dict[str, OccurrenceWindow]:
        """Read the ordered journal stream into its currently live windows."""
        return fold(self._journal.read(), now=now)


def _occurrence(event: Event) -> tuple[str, str, str | None]:
    try:
        signature = event.body["signature"]
        occurrence_id = event.body["occurrence_id"]
        emitting_stage = event.body["emitting_stage"]
        _validate_identity(signature, occurrence_id, emitting_stage)
        if (set(event.body) != {"kind", "signature", "occurrence_id", "emitting_stage"}
                or event.key != f"{_KEY_PREFIX}/{signature}/{occurrence_id}"):
            raise ValueError("storm occurrence does not have its durable identity")
    except (KeyError, ValueError) as error:
        raise JournalCorruption(f"invalid storm occurrence {event.key!r}: {error}") from error
    return signature, occurrence_id, emitting_stage


def _validate_identity(signature: object, occurrence_id: object,
                       emitting_stage: object) -> None:
    if (not isinstance(signature, str) or not signature
            or not isinstance(occurrence_id, str) or not occurrence_id
            or (emitting_stage is not None and not isinstance(emitting_stage, str))):
        raise ValueError("storm occurrence needs nonempty string identities and optional stage")
