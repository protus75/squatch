"""Phase 0 exit read 3 (plan section 19; section 15 harness rung 2): the
crash-point / fault-injection harness over the state layer (journal +
effects). Emitter: this harness.

Crash model. The state layer's one durable surface is the active journal
segment: an append-only file written one record at a time, each record
fsync'd before the next begins. A crash at ANY instant therefore leaves a
PREFIX of the bytes an uninterrupted run would have written -- a whole
number of records plus, at most, a torn tail of the record in flight. The
harness induces that crash two ways and restarts the state layer over the
crashed directory each time:

  1. at every named write point of one effect's lifecycle -- before, mid
     (torn at three offsets), and after each of its two records, with the
     action run or not run as the point dictates;
  2. at every byte offset of a finished multi-effect segment.

Invariants read back after every restart:
  - torn-tail tolerance: the reader yields exactly the whole records, in
    order; the resumed writer drops the torn tail and appends cleanly, so
    the segment never carries a malformed line mid-file;
  - effect once-semantics: an action whose completion record is durable
    never runs again, on this restart or any later one; an action whose
    completion is NOT durable runs at most once more (the intent-only
    window is a single re-execution -- Phase 1 reconcile closes it -- and
    a further restart never widens it).
"""

import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from squatch.effects import Effects
from squatch.journal import Journal

T0 = datetime(2026, 8, 4, 12, 30, 15, tzinfo=timezone.utc)
KEY = "git/T-1/1/push"
TICKET = "T-1"
INTENT, COMPLETION = "effect_intent", "effect_completion"


class TickingClock:
    def __init__(self, start=T0):
        self.now = start

    def __call__(self):
        self.now += timedelta(seconds=1)
        return self.now


class Crash(Exception):
    """The induced process death: nothing after it runs in the dying process."""


class Counter:
    """The external action: every execution is a visible side effect."""

    def __init__(self):
        self.calls = 0

    async def action(self):
        self.calls += 1
        return {"n": self.calls}


def segment(state_dir: Path) -> Path:
    return state_dir / "journal" / "000001-20260804.jsonl"


def whole_lines(data: bytes) -> list[bytes]:
    return data.split(b"\n")[:-1]


def tear(path: Path, keep: str) -> None:
    """Truncate the just-written last record to a prefix of itself."""
    data = path.read_bytes()
    start = data.rfind(b"\n", 0, len(data) - 1) + 1
    line = data[start:]
    n = {"first_byte": 1, "half": len(line) // 2, "no_newline": len(line) - 1}[keep]
    assert 0 < n < len(line)
    with path.open("r+b") as f:
        f.truncate(start + n)
        f.flush()
        os.fsync(f.fileno())


@dataclass(frozen=True)
class CrashPoint:
    record: str  # the record whose write point the crash lands on
    when: str    # before | torn | after
    keep: str | None = None  # torn only: how much of the record survives

    @property
    def action_ran(self) -> bool:
        # Effects runs the action between the two records.
        return self.record == COMPLETION

    @property
    def completion_durable(self) -> bool:
        return self.record == COMPLETION and self.when == "after"

    @property
    def durable_records(self) -> list[str]:
        if self.record == INTENT:
            return [INTENT] if self.when == "after" else []
        return [INTENT, COMPLETION] if self.when == "after" else [INTENT]

    def __str__(self):
        return f"{self.record}/{self.when}" + (f"/{self.keep}" if self.keep else "")


POINTS = [
    CrashPoint(record, when, keep)
    for record in (INTENT, COMPLETION)
    for when, keep in (("before", None), ("torn", "first_byte"), ("torn", "half"),
                       ("torn", "no_newline"), ("after", None))
]


class FaultJournal:
    """Wraps the real journal and dies at one write point of one record type.
    `before` dies with nothing written; `after` dies once the record is
    fsync'd; `torn` dies mid-write, leaving a prefix of the record."""

    def __init__(self, inner: Journal, point: CrashPoint, path: Path):
        self._inner = inner
        self._point = point
        self._path = path

    def append(self, type, body, **kw):
        if type != self._point.record:
            return self._inner.append(type, body, **kw)
        if self._point.when == "before":
            raise Crash(f"before {type}")
        self._inner.append(type, body, **kw)
        if self._point.when == "torn":
            tear(self._path, self._point.keep)
        raise Crash(f"{self._point.when} {type}")

    def read(self):
        return self._inner.read()


def types(journal: Journal) -> list[str]:
    return [e.type for e in journal.read()]


async def crash_at(state_dir: Path, point: CrashPoint, counter: Counter) -> None:
    with Journal(state_dir, clock=TickingClock()) as j:
        with pytest.raises(Crash):
            await Effects(FaultJournal(j, point, segment(state_dir))).run(counter.action, key=KEY, ticket=TICKET)


async def restart_and_run(state_dir: Path, counter: Counter):
    """One process lifetime after the crash: open the state layer, read what
    survived, run the same effect key, read what the run left."""
    with Journal(state_dir, clock=TickingClock()) as j:
        survived = types(j)
        result = await Effects(j).run(counter.action, key=KEY, ticket=TICKET)
        after = types(j)
    return survived, result, after


# --- 1. named crash points of one effect's lifecycle -------------------------


@pytest.mark.parametrize("point", POINTS, ids=str)
async def test_crash_at_every_write_point_then_restart(tmp_path, point):
    counter = Counter()
    await crash_at(tmp_path, point, counter)
    assert counter.calls == (1 if point.action_ran else 0)

    survived, result, after = await restart_and_run(tmp_path, counter)

    # Torn-tail tolerance: exactly the durable records come back, in order,
    # and the resumed writer left no partial line behind.
    assert survived == point.durable_records
    data = segment(tmp_path).read_bytes()
    assert data.endswith(b"\n")
    assert len(whole_lines(data)) == len(after)
    for line in whole_lines(data):
        json.loads(line)

    # Once-semantics.
    if point.completion_durable:
        assert result == {"n": 1}
        assert counter.calls == 1
        assert after == survived
    else:
        assert counter.calls == (2 if point.action_ran else 1)
        assert result == {"n": counter.calls}
        assert after == survived + [INTENT, COMPLETION]

    # The window never widens: every later restart replays the recorded result.
    calls = counter.calls
    for _ in range(2):
        _, again, later = await restart_and_run(tmp_path, counter)
        assert again == result
        assert counter.calls == calls
        assert later == after


# --- 2. every byte offset of a finished multi-effect segment -----------------


KEYS = ("git/T-1/1/rebase", "git/T-1/1/merge", "notify/T-1/merged")


async def reference_run(state_dir: Path) -> bytes:
    """The uninterrupted run whose byte prefixes are the crash states."""
    counter = Counter()
    with Journal(state_dir, clock=TickingClock()) as j:
        fx = Effects(j)
        for key in KEYS:
            await fx.run(counter.action, key=key, ticket=TICKET)
    return segment(state_dir).read_bytes()


def crashed_dir(root: Path, full: bytes, cut: int) -> Path:
    """A state dir as a crash at byte `cut` of the reference run leaves it."""
    state = root / "crashed"
    shutil.rmtree(state, ignore_errors=True)
    segment(state).parent.mkdir(parents=True)
    segment(state).write_bytes(full[:cut])
    return state


def durable_prefix(records: list[dict], line_ends: list[int], cut: int) -> list[dict]:
    return records[:sum(1 for end in line_ends if end <= cut)]


async def test_every_crash_prefix_reads_back_as_exactly_the_whole_records(tmp_path):
    """Every byte offset: the reader yields the whole records and nothing of
    the torn tail, whatever bytes the tail holds, and the resumed writer
    truncates the segment to exactly those records."""
    full = await reference_run(tmp_path / "reference")
    records = [json.loads(line) for line in whole_lines(full)]
    line_ends = [i + 1 for i, b in enumerate(full) if b == ord("\n")]
    assert len(records) == 2 * len(KEYS)

    for cut in range(len(full) + 1):
        state = crashed_dir(tmp_path, full, cut)
        durable = durable_prefix(records, line_ends, cut)
        with Journal(state, clock=TickingClock()) as j:
            assert [(e.type, e.key) for e in j.read()] == [
                (r["type"], r["key"]) for r in durable], f"cut={cut}"
        assert segment(state).read_bytes() == full[:line_ends[len(durable) - 1] if durable else 0]


def crash_classes(full: bytes, line_ends: list[int]) -> list[int]:
    """Per record, one offset from each crash-state class: none of it, its
    first byte, half of it, all but its newline, and the whole record."""
    offsets = set()
    for start, end in zip([0, *line_ends[:-1]], line_ends):
        n = end - start
        offsets.update(start + k for k in (0, 1, n // 2, n - 1, n))
    return sorted(offsets)


async def test_restart_after_every_crash_class_replays_completed_keys_and_runs_the_rest_once(tmp_path):
    full = await reference_run(tmp_path / "reference")
    records = [json.loads(line) for line in whole_lines(full)]
    line_ends = [i + 1 for i, b in enumerate(full) if b == ord("\n")]

    for cut in crash_classes(full, line_ends):
        state = crashed_dir(tmp_path, full, cut)
        durable = durable_prefix(records, line_ends, cut)
        completed = {r["key"] for r in durable if r["type"] == COMPLETION}
        # A durable intent with no completion is inert history; its key
        # re-executes and appends a fresh pair after everything that survived.
        recovered = [r["type"] for r in durable] + [
            INTENT, COMPLETION] * (len(KEYS) - len(completed))

        with Journal(state, clock=TickingClock()) as j:
            counter = Counter()
            fx = Effects(j)
            results = {key: await fx.run(counter.action, key=key, ticket=TICKET)
                       for key in KEYS}
            assert counter.calls == len(KEYS) - len(completed), f"cut={cut}"
            for key in completed:
                assert results[key] == next(
                    r["body"]["result"] for r in durable
                    if r["type"] == COMPLETION and r["key"] == key), f"cut={cut}"
            assert types(j) == recovered, f"cut={cut}"

        # The recovered segment is whole and the window never widens: a second
        # restart reads every line and runs nothing.
        with Journal(state, clock=TickingClock()) as j:
            assert types(j) == recovered, f"cut={cut}"
            assert segment(state).read_bytes().endswith(b"\n")
            fx = Effects(j)
            for key in KEYS:
                assert await fx.run(counter.action, key=key, ticket=TICKET) == results[key]
            assert counter.calls == len(KEYS) - len(completed), f"cut={cut}"


async def test_crash_before_the_first_record_leaves_an_openable_state_dir(tmp_path):
    """The segment file may exist and be empty, or not exist at all (its
    directory entry never fsync'd); both restart clean."""
    for shape in ("empty_file", "no_file"):
        state = tmp_path / shape
        segment(state).parent.mkdir(parents=True)
        if shape == "empty_file":
            segment(state).write_bytes(b"")
        counter = Counter()
        with Journal(state, clock=TickingClock()) as j:
            assert types(j) == []
            assert await Effects(j).run(counter.action, key=KEY, ticket=TICKET) == {"n": 1}
        with Journal(state, clock=TickingClock()) as j:
            assert await Effects(j).run(counter.action, key=KEY, ticket=TICKET) == {"n": 1}
            assert types(j) == [INTENT, COMPLETION]
        assert counter.calls == 1
