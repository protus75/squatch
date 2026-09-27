"""Journal-derived, per-ticket storm dispatch holds in the live drain."""

from datetime import datetime, timezone
from io import StringIO
from uuid import UUID, uuid4

import pytest

import squatch.__main__ as main_module
from squatch.__main__ import _AdmissionDispatchPause
from squatch.box import Box
from squatch.control import ControlRequest, publish_control
from squatch.daemon import (StormDispatchHold, compose_daemon_control,
                            compose_daemon_storm_producer)
from squatch.journal import Journal, read_events
from squatch.mergequeue import Candidate
from squatch.seams import LocalFilesystem
from squatch.storm import StormLedger, _trip_id
from test_cli import STATE, author, checkout, git_env  # noqa: F401
from test_drain import Scripted


NOW = datetime(2026, 9, 27, 12, tzinfo=timezone.utc)


def _trip(journal, *, origin="candidate", signature="storm"):
    ledger = StormLedger(journal=journal)
    for number in range(6):
        ledger.record(signature=signature, occurrence_id=f"arrival-{number}",
                      emitting_stage="implement", emitting_origin=origin)
    [crossing] = [crossing for crossing in ledger.crossings()
                  if crossing["signature"] == signature]
    assert ledger.trip(crossing)
    return crossing


def test_origin_is_nullable_durable_legacy_compatible_and_producer_supplied(tmp_path):
    fs = LocalFilesystem()
    with Journal(tmp_path / "new", clock=lambda: NOW) as journal:
        ledger = StormLedger(journal=journal)
        assert ledger.record(signature="nullable", occurrence_id="one")
        event = tuple(journal.read())[0]
        assert event.body["emitting_origin"] is None
        with pytest.raises(ValueError, match="optional stage and origin"):
            ledger.record(signature="nullable", occurrence_id="bad", emitting_origin=7)

    legacy = tmp_path / "legacy"
    trip_id = _trip_id("old", "first", "crossing")
    with Journal(legacy, clock=lambda: NOW) as journal:
        journal.append("signal", {
            "kind": "storm_occurrence", "signature": "old", "occurrence_id": "first",
            "emitting_stage": None,
        }, key="storm-occurrence/old/first")
        journal.append("signal", {
            "kind": "storm_trip", "trip_id": trip_id, "signature": "old",
            "first_live_occurrence_id": "first", "crossing_occurrence_id": "crossing",
            "emitting_stage": None,
        }, key=f"storm-trip/{trip_id}")
        ledger = StormLedger(journal=journal)
        assert ledger.window(now=NOW)["old"].occurrence_ids == ("first",)
        assert ledger.trips()[0]["emitting_origin"] is None

    produced = tmp_path / "produced"
    with Journal(produced, clock=lambda: NOW) as journal:
        box = Box(produced, fs=fs, clock=lambda: NOW)
        with compose_daemon_storm_producer(
                state_dir=produced, journal=journal, fs=fs, clock=lambda: NOW):
            for _ in range(6):
                message = box.enqueue(message_class="suggestion", summary="same",
                                      detail="same", origin="candidate", stage="review")
        occurrences = [event for event in journal.read()
                       if event.body.get("kind") == "storm_occurrence"]
        [trip] = StormLedger(journal=journal).trips()
        [trip_event] = [event for event in journal.read()
                        if event.body.get("kind") == "storm_trip"]
        assert {event.body["emitting_origin"] for event in occurrences} == {"candidate"}
        assert trip["emitting_origin"] == "candidate"
        assert set(trip_event.body) == {
            "kind", "trip_id", "signature", "first_live_occurrence_id",
            "crossing_occurrence_id", "emitting_stage", "emitting_origin"}
        assert trip["trip_id"] == _trip_id(
            occurrences[0].body["signature"], f"{message.id}/1", f"{message.id}/6")


@pytest.mark.asyncio
async def test_hold_decision_precedes_mutation_and_release_preserves_other_owners(
        tmp_path, monkeypatch):
    fs = LocalFilesystem()
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        inbox = compose_daemon_control(state_dir=tmp_path, journal=journal, fs=fs)
        pause = _AdmissionDispatchPause(inbox, journal)
        manual = ControlRequest(action="pause", lifecycle=inbox.lifecycle)
        publish_control(tmp_path, manual, fs)
        assert not await pause.allow_offer()
        manual_hold = pause.hold_id

        premature = ControlRequest(
            action="release", lifecycle=inbox.lifecycle, hold_id=uuid4())
        publish_control(tmp_path, premature, fs)
        [decision] = await inbox.consume(pause.apply)
        assert decision.outcome == "stale"

        crossing = _trip(journal)
        observed = []
        rehydrate = inbox.rehydrate_holds

        def decision_first():
            [event] = [event for event in journal.read()
                       if event.body.get("trigger") == "storm_trip"]
            assert event.body["trip_id"] == crossing["trip_id"]
            observed.append(event.body["hold_id"])
            rehydrate()

        monkeypatch.setattr(inbox, "rehydrate_holds", decision_first)
        assert pause.holds_offer("candidate")
        storm_hold = UUID(observed[0])
        monkeypatch.setattr(inbox, "rehydrate_holds", rehydrate)
        pause.admission_hold.trip(
            Candidate(stem="integration", branch="integration", worktree=tmp_path, run_seq=1),
            trigger="tree_hash_mismatch")
        admission_hold = pause.admission_hold.hold_id
        assert {manual_hold, storm_hold, admission_hold} <= inbox.holds

        for request in (
            ControlRequest(action="release", lifecycle=inbox.lifecycle, hold_id=uuid4()),
            ControlRequest(action="release", lifecycle=uuid4(), hold_id=storm_hold),
        ):
            publish_control(tmp_path, request, fs)
        decisions = await inbox.consume(pause.apply)
        assert [decision.outcome for decision in decisions] == ["stale", "stale"]
        assert pause.holds_offer("candidate")

        release = ControlRequest(
            action="release", lifecycle=inbox.lifecycle, hold_id=storm_hold)
        publish_control(tmp_path, release, fs)
        await inbox.consume(pause.apply)
        assert not pause.holds_offer("candidate")
        assert manual_hold in inbox.holds and admission_hold in inbox.holds

        _trip(journal, signature="later")
        assert pause.holds_offer("candidate")
        later_hold = next(hold for hold in inbox.holds
                          if hold not in {manual_hold, admission_hold})
        publish_control(tmp_path, release, fs)
        await inbox.consume(pause.apply)
        assert pause.holds_offer("candidate") and later_hold in inbox.holds


def test_trip_hold_recovers_after_decision_append_crash(tmp_path, monkeypatch):
    fs = LocalFilesystem()
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        inbox = compose_daemon_control(state_dir=tmp_path, journal=journal, fs=fs)
        storm = StormDispatchHold(inbox, journal)
        _trip(journal)

        def crash():
            raise RuntimeError("crash after decision")

        monkeypatch.setattr(inbox, "rehydrate_holds", crash)
        with pytest.raises(RuntimeError, match="crash after decision"):
            storm.holds_offer("candidate")
        lifecycle = inbox.lifecycle

    monkeypatch.undo()
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        inbox = compose_daemon_control(state_dir=tmp_path, journal=journal, fs=fs)
        storm = StormDispatchHold(inbox, journal)
        assert inbox.lifecycle == lifecycle
        assert storm.holds_offer("candidate")
        assert len(inbox.holds) == 1


def test_live_root_skips_matching_stem_before_accounting_then_resumes(
        checkout, monkeypatch):
    author(checkout, "candidate")
    author(checkout, "unrelated")
    state = checkout / STATE
    fs = LocalFilesystem()
    box = Box(state, fs=fs, clock=lambda: NOW)
    for _ in range(6):
        box.enqueue(message_class="suggestion", summary="same", detail="same",
                    origin="candidate", stage="implement")

    original = main_module._control_factory
    resumed = []

    async def resume(_seconds):
        events = tuple(read_events(state))
        [hold] = [event for event in events if event.body.get("trigger") == "storm_trip"]
        assert hold.ticket == "candidate"
        assert not any(event.ticket == "candidate" and event.type in {
            "state_transition", "cap_consumed", "effect_intent"} for event in events)
        assert any(event.ticket == "unrelated" and event.type == "state_transition"
                   for event in events)
        assert main_module.main(
            ["resume", "--hold-id", hold.body["hold_id"]], cwd=checkout,
            env=git_env(checkout.parent), out=StringIO(), clock=lambda: NOW) == 0
        resumed.append(hold.body["hold_id"])

    monkeypatch.setattr(
        main_module, "_control_factory",
        lambda state_dir, supplier: original(state_dir, supplier, sleep=resume))
    pipeline = Scripted({"candidate": ["ok"], "unrelated": ["ok"]})
    out = StringIO()
    rc = main_module.main(
        ["drain"], cwd=checkout, env=git_env(checkout.parent), out=out,
        pipeline=pipeline, clock=lambda: NOW)

    assert rc == 0, out.getvalue()
    assert [stem for stem, _ in pipeline.calls] == ["unrelated", "candidate"]
    assert len(resumed) == 1
    events = tuple(read_events(state))
    hold_index = next(i for i, event in enumerate(events)
                      if event.body.get("trigger") == "storm_trip")
    candidate_index = next(i for i, event in enumerate(events)
                           if event.ticket == "candidate"
                           and event.body.get("to") == "running")
    assert hold_index < candidate_index


def test_null_and_nonmatching_origins_do_not_create_a_global_hold(tmp_path):
    fs = LocalFilesystem()
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        inbox = compose_daemon_control(state_dir=tmp_path, journal=journal, fs=fs)
        storm = StormDispatchHold(inbox, journal)
        _trip(journal, origin=None, signature="null")
        _trip(journal, origin="not-a-ticket", signature="external")
        assert not storm.holds_offer("candidate")
        assert inbox.holds == frozenset()
        assert not any(event.body.get("trigger") == "storm_trip" for event in journal.read())


def test_matching_reoffer_is_held_before_its_retry_draw(checkout, monkeypatch):
    author(checkout, "candidate")
    state = checkout / STATE
    fs = LocalFilesystem()
    box = Box(state, fs=fs, clock=lambda: NOW)
    for _ in range(6):
        box.enqueue(message_class="suggestion", summary="same", detail="same",
                    origin="candidate", stage="implement")
    with Journal(state, clock=lambda: NOW) as journal:
        journal.append("state_transition", {"to": "gate_failed", "run_seq": 0},
                       ticket="candidate")

    original = main_module._control_factory
    checked = []

    async def resume(_seconds):
        events = tuple(read_events(state))
        [hold] = [event for event in events if event.body.get("trigger") == "storm_trip"]
        assert not any(event.ticket == "candidate" and event.type == "cap_consumed"
                       for event in events)
        assert main_module.main(
            ["resume", "--hold-id", hold.body["hold_id"]], cwd=checkout,
            env=git_env(checkout.parent), out=StringIO(), clock=lambda: NOW) == 0
        checked.append(True)

    monkeypatch.setattr(
        main_module, "_control_factory",
        lambda state_dir, supplier: original(state_dir, supplier, sleep=resume))
    pipeline = Scripted({"candidate": ["ok"]})
    assert main_module.main(
        ["drain"], cwd=checkout, env=git_env(checkout.parent), out=StringIO(),
        pipeline=pipeline, clock=lambda: NOW) == 0

    events = tuple(read_events(state))
    hold_index = next(i for i, event in enumerate(events)
                      if event.body.get("trigger") == "storm_trip")
    draw_index = next(i for i, event in enumerate(events)
                      if event.ticket == "candidate" and event.type == "cap_consumed")
    running_index = next(i for i, event in enumerate(events)
                         if event.ticket == "candidate" and event.body.get("to") == "running")
    assert checked == [True] and hold_index < draw_index < running_index
