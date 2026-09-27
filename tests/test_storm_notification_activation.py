"""Storm trips and reports through the lock-held production composition."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest

import squatch.__main__ as main_module
import squatch.daemon as daemon_module
from squatch.artifacts import Cost
from squatch.box import (Box, STORM_BREAKER_ORIGIN, enqueue_second_problems,
                         main as box_main)
from squatch.daemon import compose_daemon_storm_producer
from squatch.journal import Journal, read_events
from squatch.lockfile import LockHeld, Lockfile
from squatch.seams import LocalFilesystem
from squatch.stages import Delivery, Verification
from squatch.storm import THRESHOLD, WINDOW, StormLedger, _trip_id
from test_cli import STATE, author, checkout, git_env  # noqa: F401
from test_drain import Scripted


T0 = datetime(2026, 9, 27, 12, tzinfo=timezone.utc)


class Clock:
    def __init__(self, now=T0):
        self.now = now

    def __call__(self):
        return self.now


def trips(events):
    return [event for event in events if event.body.get("kind") == "storm_trip"]


def occurrences(events):
    return [event for event in events if event.body.get("kind") == "storm_occurrence"]


def reports(box):
    return [message for _, message in box._records()
            if message.message_class == "failure_report"
            and message.origin.startswith(STORM_BREAKER_ORIGIN)]


def enqueue_same(box, *, stage=None):
    return box.enqueue(message_class="suggestion", summary="same", detail="same",
                       origin="producer", stage=stage)


def observe_timer_shutdown(monkeypatch):
    stopped = []
    original = daemon_module.compose_daemon_timers

    def compose(**kwargs):
        timers = original(**kwargs)
        shutdown = timers.shutdown

        async def stop():
            assert not kwargs["journal"].closed
            await shutdown()
            stopped.append(True)

        timers.shutdown = stop
        return timers

    monkeypatch.setattr(daemon_module, "compose_daemon_timers", compose)
    return stopped


def test_main_run_binds_preconstructed_boxes_for_harvest_and_verification_paths(
        checkout, monkeypatch):
    author(checkout, "candidate")
    state = checkout / STATE
    clock = Clock()
    fs = LocalFilesystem()
    preconstructed = Box(state, fs=fs, clock=clock)
    stopped = observe_timer_shutdown(monkeypatch)

    class Pipeline:
        async def run(self, ticket, *, run_seq):
            probe = Lockfile(state, instance_id="probe", clock=clock)
            with pytest.raises(LockHeld):
                probe.acquire()
            enqueue_second_problems(
                preconstructed,
                "## Second problems filed\n- adjacent production problem\n",
                stem=ticket.stem, stage="implement", outcome="gate_failed",
                run_seq=run_seq)
            verification = Verification(
                None, checkout, None, None, {}, lambda value: value,
                box=preconstructed, run_seq=run_seq)
            verification._file_base_red(
                SimpleNamespace(stem=ticket.stem), "verification command exit 1")
            return Delivery("ok", [], None, None, None, Path("/unused"), "HEAD",
                            "merge", None, Cost(tokens=0, seconds=0, attempts=0))

        async def diagnose(self, ticket, delivery, *, run_seq):
            raise AssertionError("settled work is not diagnosed")

    out = StringIO()
    rc = main_module.main(
        ["run", "candidate"], cwd=checkout, env=git_env(checkout.parent), out=out,
        pipeline=lambda _journal: Pipeline(), clock=clock)

    assert rc == 0, out.getvalue()
    events = tuple(read_events(state))
    messages = preconstructed._records()
    production = [message for _, message in messages
                  if not message.origin.startswith(STORM_BREAKER_ORIGIN)]
    assert [(message.message_class, message.stage, message.outcome) for message in production] == [
        ("suggestion", "implement", "gate_failed"),
        ("failure_report", "check", "base_red"),
    ]
    assert {event.body["signature"] for event in occurrences(events)} == {
        message.signature for message in production}
    assert stopped == [True]
    before = len(occurrences(events))
    preconstructed.enqueue(message_class="suggestion", summary="after", detail="after",
                           origin="after")
    assert len(occurrences(tuple(read_events(state)))) == before
    with Lockfile(state, instance_id="after", clock=clock):
        pass


def test_main_run_exception_unwinds_binding_timer_and_lock(checkout, monkeypatch):
    author(checkout, "candidate")
    state = checkout / STATE
    clock = Clock()
    box = Box(state, fs=LocalFilesystem(), clock=clock)
    stopped = observe_timer_shutdown(monkeypatch)

    class Pipeline:
        async def run(self, ticket, *, run_seq):
            box.enqueue(message_class="suggestion", summary="during", detail="during",
                        origin=ticket.stem)
            raise RuntimeError("pipeline failed")

    out = StringIO()
    rc = main_module.main(
        ["run", "candidate"], cwd=checkout, env=git_env(checkout.parent), out=out,
        pipeline=lambda _journal: Pipeline(), clock=clock)

    assert rc == 2 and "pipeline failed" in out.getvalue()
    assert stopped == [True]
    assert len(occurrences(tuple(read_events(state)))) == 1
    box.enqueue(message_class="suggestion", summary="after", detail="after", origin="after")
    assert len(occurrences(tuple(read_events(state)))) == 1
    with Lockfile(state, instance_id="after-failure", clock=clock):
        pass


def test_crossing_rule_boundaries_and_trip_identity_are_replay_stable(tmp_path):
    fs, clock = LocalFilesystem(), Clock()
    first_state = tmp_path / "first"
    with Journal(first_state, clock=clock) as journal:
        box = Box(first_state, fs=fs, clock=clock)
        with compose_daemon_storm_producer(
                state_dir=first_state, journal=journal, fs=fs, clock=clock):
            for _ in range(THRESHOLD):
                enqueue_same(box)
            assert trips(tuple(journal.read())) == []
            crossing = enqueue_same(box)
            first_trip = trips(tuple(journal.read()))[0]
            for _ in range(THRESHOLD):
                enqueue_same(box)
            assert len(trips(tuple(journal.read()))) == 1
            assert first_trip.body["emitting_stage"] is None

            clock.now += WINDOW
            for _ in range(THRESHOLD):
                enqueue_same(box)
            assert len(trips(tuple(journal.read()))) == 1
            enqueue_same(box)
            assert len(trips(tuple(journal.read()))) == 2

            for _ in range(THRESHOLD):
                box.enqueue(message_class="suggestion", summary="inside", detail="inside",
                            origin="inside", stage="check")
            clock.now += WINDOW - timedelta(microseconds=1)
            box.enqueue(message_class="suggestion", summary="inside", detail="inside",
                        origin="inside", stage="check")
            assert len(trips(tuple(journal.read()))) == 3

        first_occurrences = occurrences(tuple(journal.read()))[:THRESHOLD + 1]

    signature = first_occurrences[0].body["signature"]
    first_id = first_occurrences[0].body["occurrence_id"]
    crossing_id = f"{crossing.id}/{THRESHOLD + 1}"
    canonical = json.dumps(
        [signature, first_id, crossing_id], ensure_ascii=False,
        separators=(",", ":")).encode()
    assert first_trip.body["trip_id"] == hashlib.sha256(canonical).hexdigest()
    assert len({_trip_id(signature, first_id, crossing_id),
                _trip_id(signature + "x", first_id, crossing_id),
                _trip_id(signature, first_id + "x", crossing_id),
                _trip_id(signature, first_id, crossing_id + "x")}) == 4

    replay_state = tmp_path / "replay"
    replay_clock = Clock()
    with Journal(replay_state, clock=replay_clock) as replay:
        ledger = StormLedger(journal=replay)
        for event in first_occurrences:
            ledger.record(signature=event.body["signature"],
                          occurrence_id=event.body["occurrence_id"],
                          emitting_stage=event.body["emitting_stage"])
        assert ledger.crossings()[0]["trip_id"] == first_trip.body["trip_id"]


def test_rolled_occurrence_recovery_reuses_resolved_report_without_recursion(tmp_path):
    fs, clock = LocalFilesystem(), Clock()
    with Journal(tmp_path, clock=clock) as journal:
        ledger = StormLedger(journal=journal)
        for number in range(THRESHOLD + 1):
            ledger.record(signature="persisted", occurrence_id=f"arrival-{number}",
                          emitting_stage="review")
        assert ledger.crossings() and not trips(tuple(journal.read()))
        clock.now += timedelta(hours=25)
        journal.append("signal", {"kind": "unrelated"})
        assert len(journal.segments()) == 2

        with compose_daemon_storm_producer(
                state_dir=tmp_path, journal=journal, fs=fs, clock=clock):
            pass
        box = Box(tmp_path, fs=fs, clock=clock)
        [report] = reports(box)
        assert report.reports == 1
        assert "arrival-0" in report.detail and f"arrival-{THRESHOLD}" in report.detail
        box.resolve(report.id, status="decided", link="fixed", note="resolved")

        for _ in range(2):
            with compose_daemon_storm_producer(
                    state_dir=tmp_path, journal=journal, fs=fs, clock=clock):
                pass
        [reused] = reports(box)
        events = tuple(journal.read())
        assert reused.status == "decided" and reused.reports == 1
        assert len(trips(events)) == 1
        assert not any(event.body["signature"] == reused.signature
                       for event in occurrences(events))


def test_trip_before_report_crash_repairs_exactly_one_report(tmp_path):
    fs, clock = LocalFilesystem(), Clock()
    with Journal(tmp_path, clock=clock) as journal:
        ledger = StormLedger(journal=journal)
        for number in range(THRESHOLD + 1):
            ledger.record(signature="crashed", occurrence_id=f"arrival-{number}")
        [crossing] = ledger.crossings()
        assert ledger.trip(crossing)
        assert not (tmp_path / "box").exists()

        for _ in range(2):
            with compose_daemon_storm_producer(
                    state_dir=tmp_path, journal=journal, fs=fs, clock=clock):
                pass
        box = Box(tmp_path, fs=fs, clock=clock)
        [report] = reports(box)
        assert report.reports == 1
        assert len(trips(tuple(journal.read()))) == 1


def test_unbound_enqueue_writes_no_journal_and_cli_ingest_refuses_the_live_lock(
        checkout, capsys):
    state = checkout / STATE
    clock = Clock()
    box = Box(state, fs=LocalFilesystem(), clock=clock)
    enqueue_same(box)
    assert not (state / "journal").exists()

    source = checkout / "ideas.md"
    source.write_text("another idea\n")
    before = tuple(box._records())
    with Lockfile(state, instance_id="running-engine", clock=clock):
        assert box_main(["ingest", str(source)], cwd=checkout) == 2
    captured = capsys.readouterr()
    assert "engine holds the instance lock" in captured.err
    assert "paved road:" in captured.err and "re-run `ingest`" in captured.err
    assert tuple(box._records()) == before


def test_cli_ingest_refuses_invalid_state_directory_with_paved_road(checkout, capsys):
    state = checkout / STATE
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text("not a directory")
    source = checkout / "ideas.md"
    source.write_text("another idea\n")

    assert box_main(["ingest", str(source)], cwd=checkout) == 2

    captured = capsys.readouterr()
    assert "refused: cannot ingest into" in captured.err
    assert "paved road:" in captured.err
    assert "state directory permissions, then re-run `ingest`" in captured.err
    assert "Traceback" not in captured.err
    assert state.read_text() == "not a directory"


def test_real_drain_dispatches_after_trip_without_a_storm_control_hold(checkout):
    author(checkout, "candidate")
    state = checkout / STATE
    clock = Clock()
    box = Box(state, fs=LocalFilesystem(), clock=clock)
    for _ in range(THRESHOLD + 1):
        enqueue_same(box, stage="implement")
    pipeline = Scripted({"candidate": ["ok"]})
    out = StringIO()

    rc = main_module.main(
        ["drain"], cwd=checkout, env=git_env(checkout.parent), out=out,
        pipeline=pipeline, clock=clock)

    events = tuple(read_events(state))
    assert rc == 0, out.getvalue()
    assert pipeline.calls == [("candidate", 0)]
    assert len(trips(events)) == 1 and len(reports(box)) == 1
    assert not any(event.body.get("kind") == "control_hold" for event in events)
