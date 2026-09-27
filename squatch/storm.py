"""Dormant, journal-backed storm occurrence window."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json

from squatch.journal import Event, Journal, JournalCorruption, render_ts


THRESHOLD = 5
WINDOW = timedelta(hours=1)
_KIND = "storm_occurrence"
_KEY_PREFIX = "storm-occurrence"
_TRIP_KIND = "storm_trip"
_TRIP_KEY_PREFIX = "storm-trip"


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
        signature, occurrence_id, emitting_stage, emitting_origin = _occurrence(event)
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
               emitting_stage: str | None = None,
               emitting_origin: str | None = None) -> bool:
        """Append an occurrence once, returning whether this call wrote it."""
        _validate_identity(signature, occurrence_id, emitting_stage, emitting_origin)
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
            "emitting_origin": emitting_origin,
        }, key=key)
        return True

    def window(self, *, now: datetime) -> dict[str, OccurrenceWindow]:
        """Read the ordered journal stream into its currently live windows."""
        return fold(self._journal.read(), now=now)

    def crossings(self) -> tuple[dict, ...]:
        """Recover every historical threshold crossing at its occurrence time."""
        live_by_signature: dict[str, list[tuple[str, datetime]]] = {}
        crossings: list[dict] = []
        for event in self._journal.read():
            if event.type != "signal" or event.body.get("kind") != _KIND:
                continue
            signature, occurrence_id, emitting_stage, emitting_origin = _occurrence(event)
            now = datetime.fromisoformat(event.ts)
            lower = now - WINDOW
            live = live_by_signature.setdefault(signature, [])
            live[:] = [item for item in live if lower < item[1] <= now]
            was_over_threshold = len(live) > THRESHOLD
            live.append((occurrence_id, now))
            if was_over_threshold or len(live) <= THRESHOLD:
                continue
            first_live_occurrence_id = live[0][0]
            trip_id = _trip_id(signature, first_live_occurrence_id, occurrence_id)
            crossings.append({
                "trip_id": trip_id,
                "signature": signature,
                "first_live_occurrence_id": first_live_occurrence_id,
                "crossing_occurrence_id": occurrence_id,
                "emitting_stage": emitting_stage,
                "emitting_origin": emitting_origin,
            })
        return tuple(crossings)

    def trip(self, crossing: dict) -> bool:
        """Append one deterministic trip signal, returning whether it was new."""
        crossing = {**crossing, "emitting_origin": crossing.get("emitting_origin")}
        _validate_trip(crossing)
        trip_id = crossing["trip_id"]
        key = f"{_TRIP_KEY_PREFIX}/{trip_id}"
        for event in self._journal.read():
            if event.type == "signal" and event.key == key:
                _trip(event)
                return False
        self._journal.append("signal", {"kind": _TRIP_KIND, **crossing}, key=key)
        return True

    def trips(self) -> tuple[dict, ...]:
        """Read durable trips, normalizing the legacy nullable origin."""
        return tuple(_trip(event) for event in self._journal.read()
                     if event.type == "signal" and event.body.get("kind") == _TRIP_KIND)


def _trip_id(signature: str, first_live_occurrence_id: str,
             crossing_occurrence_id: str) -> str:
    encoded = json.dumps(
        [signature, first_live_occurrence_id, crossing_occurrence_id],
        ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _occurrence(event: Event) -> tuple[str, str, str | None, str | None]:
    try:
        signature = event.body["signature"]
        occurrence_id = event.body["occurrence_id"]
        emitting_stage = event.body["emitting_stage"]
        emitting_origin = event.body.get("emitting_origin")
        _validate_identity(signature, occurrence_id, emitting_stage, emitting_origin)
        fields = {"kind", "signature", "occurrence_id", "emitting_stage"}
        if (set(event.body) not in (fields, fields | {"emitting_origin"})
                or event.key != f"{_KEY_PREFIX}/{signature}/{occurrence_id}"):
            raise ValueError("storm occurrence does not have its durable identity")
    except (KeyError, ValueError) as error:
        raise JournalCorruption(f"invalid storm occurrence {event.key!r}: {error}") from error
    return signature, occurrence_id, emitting_stage, emitting_origin


def _validate_identity(signature: object, occurrence_id: object,
                       emitting_stage: object, emitting_origin: object) -> None:
    if (not isinstance(signature, str) or not signature
            or not isinstance(occurrence_id, str) or not occurrence_id
            or (emitting_stage is not None and not isinstance(emitting_stage, str))
            or (emitting_origin is not None and not isinstance(emitting_origin, str))):
        raise ValueError(
            "storm occurrence needs nonempty string identities and optional stage and origin")


def _trip(event: Event) -> dict:
    try:
        body = dict(event.body)
        body["emitting_origin"] = body.get("emitting_origin")
        fields = {"kind", "trip_id", "signature", "first_live_occurrence_id",
                  "crossing_occurrence_id", "emitting_stage"}
        if (set(event.body) not in (fields, fields | {"emitting_origin"})
                or event.key != f"{_TRIP_KEY_PREFIX}/{body['trip_id']}"):
            raise ValueError("storm trip does not have its durable identity")
        crossing = {name: value for name, value in body.items() if name != "kind"}
        _validate_trip(crossing)
    except (KeyError, ValueError) as error:
        raise JournalCorruption(f"invalid storm trip {event.key!r}: {error}") from error
    return crossing


def _validate_trip(crossing: dict) -> None:
    signature = crossing["signature"]
    first = crossing["first_live_occurrence_id"]
    last = crossing["crossing_occurrence_id"]
    _validate_identity(signature, first, crossing["emitting_stage"],
                       crossing.get("emitting_origin"))
    _validate_identity(signature, last, crossing["emitting_stage"],
                       crossing.get("emitting_origin"))
    if crossing["trip_id"] != _trip_id(signature, first, last):
        raise ValueError("storm trip id does not match its crossing")
