"""Segmented append-only JSONL journal (SQUATCH_PLAN.md D3, section 6).

`<state_dir>/journal/` holds ordered segments named `NNNNNN-YYYYMMDD.jsonl`.
The last name in sort order is the active segment; every earlier one is
immutable. Phase 0 ships the layout, the writer, and the reader; the roll
trigger arrives with the Phase 3 daemon, so pre-daemon the active segment
grows without bound.
"""

import json
import os
import re
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from squatch.seams import Clock

EVENT_TYPES = frozenset({
    "effect_intent",
    "effect_completion",
    "signal",
    "timer_armed",
    "timer_fired",
    "cap_consumed",
    "state_transition",
    "checkpoint",
})
# Known to readers so a later engine's journal is not "unknown", never written
# by this one (D2: bounds the reconcile scan later).
RESERVED_TYPES = frozenset({"checkpoint"})

_SEGMENT_NAME = re.compile(r"\A\d{6}-\d{8}\.jsonl\Z")
_TS = re.compile(r"\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{6})?\+00:00\Z")


class JournalCorruption(Exception):
    """A record the fail-closed reader will not skip."""


def render_ts(now: datetime) -> str:
    """The one pinned `ts` rendering: aware-UTC `datetime.isoformat()`.

    Lexicographic order of the result is chronological order, so readers may
    compare `ts` as strings.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("journal ts requires an aware datetime")
    return now.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class Event:
    v: int
    type: str
    ts: str
    ticket: str | None
    key: str | None
    body: dict


def _parse_event(obj: object) -> Event:
    """Validate the fixed envelope shape; any deviation is a ValueError."""
    if not isinstance(obj, dict):
        raise ValueError("event is not a JSON object")
    if set(obj) != set(Event.__dataclass_fields__):
        raise ValueError("event top-level fields are not exactly the envelope")
    if type(obj["v"]) is not int:
        raise ValueError("v is not an integer")
    if obj["type"] not in EVENT_TYPES:
        raise ValueError(f"unknown event type {obj['type']!r}")
    if not isinstance(obj["ts"], str) or not _TS.match(obj["ts"]):
        raise ValueError("ts is not the pinned RFC 3339 +00:00 rendering")
    for field in ("ticket", "key"):
        if obj[field] is not None and not isinstance(obj[field], str):
            raise ValueError(f"{field} is neither a string nor null")
    if not isinstance(obj["body"], dict):
        raise ValueError("body is not an object")
    return Event(**obj)


class Journal:
    def __init__(self, state_dir: Path, *, clock: Clock):
        self._clock = clock
        self.dir = Path(state_dir) / "journal"
        self.dir.mkdir(parents=True, exist_ok=True)
        segments = self.segments()
        if segments:
            self._active = segments[-1]
            _truncate_torn_tail(self._active)
        else:
            self._active = self.dir / f"000001-{clock():%Y%m%d}.jsonl"
        self._fh = self._active.open("ab")
        # A newly created segment is durable only once its directory entry is.
        dir_fd = os.open(self.dir, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self) -> None:
        self._fh.close()

    def segments(self) -> list[Path]:
        """Every segment in write order (name order)."""
        paths = sorted(self.dir.glob("*.jsonl"))
        for p in paths:
            if not _SEGMENT_NAME.match(p.name):
                raise JournalCorruption(f"{p}: not a segment name")
        return paths

    def append(self, type: str, body: dict, *, ticket: str | None = None,
               key: str | None = None, v: int = 1) -> Event:
        """Append one event and fsync it before returning (write-ahead)."""
        if type in RESERVED_TYPES:
            raise ValueError(f"event type {type!r} is reserved, not emitted in v1")
        event = _parse_event({
            "v": v, "type": type, "ts": render_ts(self._clock()),
            "ticket": ticket, "key": key, "body": body,
        })
        line = json.dumps(asdict(event), allow_nan=False) + "\n"
        self._fh.write(line.encode())
        self._fh.flush()
        os.fsync(self._fh.fileno())
        return event

    def read(self) -> Iterator[Event]:
        """Every event across all segments, in order.

        Exactly one thing is tolerated: an unterminated final line of the
        active segment. Anything else malformed is corruption.
        """
        segments = self.segments()
        for path in segments:
            yield from _read_segment(path, active=path == segments[-1])


def _read_segment(path: Path, *, active: bool) -> Iterator[Event]:
    lines = path.read_bytes().split(b"\n")
    tail = lines.pop()  # bytes after the last newline: empty when well-formed
    if tail and not active:
        raise JournalCorruption(f"{path}: torn tail in an immutable segment")
    for n, raw in enumerate(lines, start=1):
        try:
            yield _parse_event(json.loads(raw))
        except ValueError as e:
            raise JournalCorruption(f"{path}:{n}: {e}") from e


def _truncate_torn_tail(path: Path) -> None:
    """The writer's startup dual of tail tolerance: drop an unterminated final
    line so a resumed append never leaves a malformed line mid-segment."""
    data = path.read_bytes()
    if data and not data.endswith(b"\n"):
        keep = data.rfind(b"\n") + 1
        with path.open("r+b") as f:
            f.truncate(keep)
            f.flush()
            os.fsync(f.fileno())
