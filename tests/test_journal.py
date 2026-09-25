"""journal.py: segmented append-only JSONL under the state dir (plan D3, section 6).

Layout and read behavior only -- the roll trigger is a Phase 3 seed and has
no test here.
"""

import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from squatch.journal import EVENT_TYPES, Event, Journal, JournalCorruption, render_ts

T0 = datetime(2026, 8, 4, 12, 30, 15, 250000, tzinfo=timezone.utc)


def fixed_clock(when=T0):
    return lambda: when


def seed_segment(journal_dir, name, events):
    journal_dir.mkdir(parents=True, exist_ok=True)
    lines = "".join(json.dumps(e) + "\n" for e in events)
    (journal_dir / name).write_text(lines)


def raw_event(n, ts=None):
    return {
        "v": 1,
        "type": "signal",
        "ts": ts or render_ts(T0 + timedelta(seconds=n)),
        "ticket": None,
        "key": None,
        "body": {"n": n},
    }


# --- ts rendering ----------------------------------------------------------


def test_render_ts_is_aware_utc_isoformat():
    assert render_ts(T0) == "2026-08-04T12:30:15.250000+00:00"
    assert render_ts(T0) == T0.isoformat()


def test_render_ts_normalizes_offsets_to_utc():
    plus_two = T0.astimezone(timezone(timedelta(hours=2)))
    assert render_ts(plus_two) == "2026-08-04T12:30:15.250000+00:00"


def test_render_ts_refuses_naive_datetime():
    with pytest.raises(ValueError):
        render_ts(T0.replace(tzinfo=None))


def test_ts_string_order_is_chronological():
    whens = [T0, T0 + timedelta(microseconds=1), T0 + timedelta(seconds=1),
             T0.replace(microsecond=0), T0 + timedelta(days=1)]
    rendered = [render_ts(w) for w in whens]
    assert sorted(rendered) == [render_ts(w) for w in sorted(whens)]


# --- layout ----------------------------------------------------------------


def test_first_append_creates_ordered_segment_under_state_dir(tmp_path):
    with Journal(tmp_path, clock=fixed_clock()) as j:
        j.append("signal", {"kind": "confirm"}, ticket="T-1")
    seg = tmp_path / "journal" / "000001-20260804.jsonl"
    assert seg.exists()
    raw = seg.read_bytes()
    assert raw.endswith(b"\n")
    assert json.loads(raw) == {
        "v": 1,
        "type": "signal",
        "ts": "2026-08-04T12:30:15.250000+00:00",
        "ticket": "T-1",
        "key": None,
        "body": {"kind": "confirm"},
    }


def test_append_then_read_round_trips(tmp_path):
    with Journal(tmp_path, clock=fixed_clock()) as j:
        a = j.append("effect_intent", {"op": "git"}, ticket="T-1", key="k1")
        b = j.append("effect_completion", {"rc": 0}, ticket="T-1", key="k1", v=2)
        assert list(j.read()) == [a, b]
    assert a == Event(v=1, type="effect_intent", ts=render_ts(T0),
                      ticket="T-1", key="k1", body={"op": "git"})
    assert b.v == 2


def test_read_across_multiple_preseeded_segments_in_name_order(tmp_path):
    jd = tmp_path / "journal"
    # Seeded out of name order so mtime order would disagree with glob order.
    seed_segment(jd, "000003-20260806.jsonl", [raw_event(5), raw_event(6)])
    seed_segment(jd, "000001-20260804.jsonl", [raw_event(1), raw_event(2)])
    seed_segment(jd, "000002-20260805.jsonl", [raw_event(3), raw_event(4)])
    with Journal(tmp_path, clock=fixed_clock()) as j:
        assert [e.body["n"] for e in j.read()] == [1, 2, 3, 4, 5, 6]
        assert [p.name for p in j.segments()] == [
            "000001-20260804.jsonl", "000002-20260805.jsonl", "000003-20260806.jsonl"]
        # The newest-named segment is the active one; no new segment is opened.
        j.append("signal", {"n": 7})
        assert [e.body["n"] for e in j.read()] == [1, 2, 3, 4, 5, 6, 7]
    assert sorted(p.name for p in jd.iterdir()) == [
        "000001-20260804.jsonl", "000002-20260805.jsonl", "000003-20260806.jsonl"]


def test_empty_journal_reads_nothing(tmp_path):
    with Journal(tmp_path, clock=fixed_clock()) as j:
        assert list(j.read()) == []


# --- durability ------------------------------------------------------------


def test_append_fsyncs_before_returning(tmp_path, monkeypatch):
    synced = []
    real_fsync = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: (synced.append(fd), real_fsync(fd)))
    with Journal(tmp_path, clock=fixed_clock()) as j:
        synced.clear()
        j.append("signal", {"n": 1})
        assert len(synced) == 1
        assert os.fstat(synced[0]).st_ino == (tmp_path / "journal" / "000001-20260804.jsonl").stat().st_ino
        j.append("signal", {"n": 2})
        assert len(synced) == 2


# --- torn tail -------------------------------------------------------------


def test_torn_final_line_of_active_segment_is_skipped(tmp_path):
    # Torn through a second handle while the Journal stays open, so the
    # reader (not the constructor's startup truncation) meets the tail.
    seg = tmp_path / "journal" / "000001-20260804.jsonl"
    with Journal(tmp_path, clock=fixed_clock()) as j:
        j.append("signal", {"n": 1})
        j.append("signal", {"n": 2})
        with seg.open("ab") as f:
            f.write(b'{"v": 1, "type": "signal", "ts": "2026-08-04T12:3')
        assert [e.body["n"] for e in j.read()] == [1, 2]


def test_writer_truncates_torn_tail_before_appending(tmp_path):
    seg = tmp_path / "journal" / "000001-20260804.jsonl"
    with Journal(tmp_path, clock=fixed_clock()) as j:
        j.append("signal", {"n": 1})
    with seg.open("ab") as f:
        f.write(b'{"v": 1, "type": "sig')
    with Journal(tmp_path, clock=fixed_clock()) as j:
        j.append("signal", {"n": 2})
        assert [e.body["n"] for e in j.read()] == [1, 2]
    lines = seg.read_bytes().split(b"\n")
    assert lines[-1] == b""
    assert [json.loads(l)["body"]["n"] for l in lines[:-1]] == [1, 2]


def test_torn_tail_in_rolled_segment_is_corruption(tmp_path):
    jd = tmp_path / "journal"
    seed_segment(jd, "000001-20260804.jsonl", [raw_event(1)])
    with (jd / "000001-20260804.jsonl").open("ab") as f:
        f.write(b'{"v": 1')
    seed_segment(jd, "000002-20260805.jsonl", [raw_event(2)])
    with Journal(tmp_path, clock=fixed_clock()) as j:
        with pytest.raises(JournalCorruption):
            list(j.read())


def test_malformed_mid_segment_line_is_corruption(tmp_path):
    jd = tmp_path / "journal"
    jd.mkdir()
    good = json.dumps(raw_event(1)) + "\n"
    (jd / "000001-20260804.jsonl").write_text(good + "not json\n" + good)
    with Journal(tmp_path, clock=fixed_clock()) as j:
        with pytest.raises(JournalCorruption):
            list(j.read())


# --- envelope --------------------------------------------------------------


def test_event_types_form_closed_set():
    assert EVENT_TYPES == frozenset({
        "effect_intent", "effect_completion", "signal", "timer_armed",
        "timer_fired", "cap_consumed", "state_transition", "checkpoint"})


def test_unknown_type_on_read_is_corruption(tmp_path):
    e = raw_event(1)
    e["type"] = "debug_chatter"
    seed_segment(tmp_path / "journal", "000001-20260804.jsonl", [e])
    with Journal(tmp_path, clock=fixed_clock()) as j:
        with pytest.raises(JournalCorruption):
            list(j.read())


@pytest.mark.parametrize("mutate", [
    lambda e: e.pop("ticket"),
    lambda e: e.update(extra="not allowed at top level"),
    lambda e: e.update(v="1"),
    lambda e: e.update(body="not an object"),
    lambda e: e.update(ts="2026-08-04T12:30:15Z"),
])
def test_envelope_shape_violation_is_corruption(tmp_path, mutate):
    e = raw_event(1)
    mutate(e)
    seed_segment(tmp_path / "journal", "000001-20260804.jsonl", [e])
    with Journal(tmp_path, clock=fixed_clock()) as j:
        with pytest.raises(JournalCorruption):
            list(j.read())


def test_append_refuses_unknown_type(tmp_path):
    with Journal(tmp_path, clock=fixed_clock()) as j:
        with pytest.raises(ValueError):
            j.append("debug_chatter", {})
        assert list(j.read()) == []


def test_append_refuses_reserved_checkpoint(tmp_path):
    with Journal(tmp_path, clock=fixed_clock()) as j:
        with pytest.raises(ValueError):
            j.append("checkpoint", {})


def test_stray_jsonl_name_in_journal_dir_is_corruption(tmp_path):
    seed_segment(tmp_path / "journal", "notes.jsonl", [raw_event(1)])
    with pytest.raises(JournalCorruption):
        Journal(tmp_path, clock=fixed_clock())
