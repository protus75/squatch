"""Segmented append-only JSONL journal (SQUATCH_PLAN.md D3, section 6).

`<state_dir>/journal/` holds ordered segments named `NNNNNN-YYYYMMDD.jsonl`.
The last name in sort order is the active segment; every earlier one is
immutable. The Phase 3 writer rolls the active segment at fixed size and age
bounds.
"""

import json
import os
import re
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
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
_MAX_SEGMENT_BYTES = 64 * 1024 * 1024
_MAX_SEGMENT_AGE = timedelta(hours=24)


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
            self._active_started = _first_event_time(self._active)
        else:
            self._active = self.dir / f"000001-{clock():%Y%m%d}.jsonl"
            self._active_started = None
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

    @property
    def closed(self) -> bool:
        """Whether the append handle is closed: the drain's self-upgrade
        handoff spawns its child only after this is true (section 18)."""
        return self._fh.closed

    def segments(self) -> list[Path]:
        """Every segment in write order (name order)."""
        return _segments(self.dir)

    def append(self, type: str, body: dict, *, ticket: str | None = None,
               key: str | None = None, v: int = 1) -> Event:
        """Append one event and fsync it before returning (write-ahead)."""
        if type in RESERVED_TYPES:
            raise ValueError(f"event type {type!r} is reserved, not emitted in v1")
        now = self._clock()
        event = _parse_event({
            "v": v, "type": type, "ts": render_ts(now),
            "ticket": ticket, "key": key, "body": body,
        })
        line = (json.dumps(asdict(event), allow_nan=False) + "\n").encode()
        if self._should_roll(now, len(line)):
            self._roll(now)
        self._fh.write(line)
        self._fh.flush()
        os.fsync(self._fh.fileno())
        if self._active_started is None:
            self._active_started = now
        return event

    def _should_roll(self, now: datetime, line_bytes: int) -> bool:
        if self._active_started is not None and now - self._active_started >= _MAX_SEGMENT_AGE:
            return True
        return self._active.stat().st_size + line_bytes > _MAX_SEGMENT_BYTES

    def _roll(self, now: datetime) -> None:
        """Seal the current segment and create the next ordered active one."""
        sequence = int(self._active.name[:6]) + 1
        next_active = self.dir / f"{sequence:06d}-{now:%Y%m%d}.jsonl"
        self._fh.close()
        self._fh = next_active.open("xb")
        self._active = next_active
        self._active_started = None
        _fsync_directory(self.dir)

    def read(self) -> Iterator[Event]:
        """Every event across all segments, in order.

        Exactly one thing is tolerated: an unterminated final line of the
        active segment. Anything else malformed is corruption.
        """
        for segment in self.read_segments():
            yield from segment

    def read_segments(self) -> Iterator[tuple[Event, ...]]:
        """Each segment's events in order, preserving segment boundaries."""
        yield from _read_segments(self.dir)


def read_segments(state_dir: Path) -> Iterator[tuple[Event, ...]]:
    """Each journal segment WITHOUT creating or repairing writer state."""
    directory = Path(state_dir) / "journal"
    if not directory.is_dir():
        return
    yield from _read_segments(directory)


def read_events(state_dir: Path) -> Iterator[Event]:
    """The projection reader: every event in order WITHOUT opening a writer.

    A projection (`status`) may run beside the lock holder, so it never
    creates the journal dir, truncates a torn tail, or holds an append handle;
    a missing journal reads as empty.
    """
    for segment in read_segments(state_dir):
        yield from segment


def _segments(directory: Path) -> list[Path]:
    paths = sorted(directory.glob("*.jsonl"))
    for p in paths:
        if not _SEGMENT_NAME.match(p.name):
            raise JournalCorruption(f"{p}: not a segment name")
    return paths


def _read_segments(directory: Path) -> Iterator[tuple[Event, ...]]:
    segments = _segments(directory)
    for path in segments:
        yield tuple(_read_segment(path, active=path == segments[-1]))


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


def _first_event_time(path: Path) -> datetime | None:
    """Return the active segment's age anchor after torn-tail repair."""
    lines = path.read_bytes().split(b"\n")
    lines.pop()
    if not lines:
        return None
    try:
        obj = json.loads(lines[0])
    except ValueError as e:
        raise JournalCorruption(f"{path}:1: {e}") from e
    if not isinstance(obj, dict) or not isinstance(obj.get("ts"), str):
        return None
    try:
        return datetime.fromisoformat(obj["ts"])
    except ValueError:
        return None


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


def _fsync_directory(directory: Path) -> None:
    dir_fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
