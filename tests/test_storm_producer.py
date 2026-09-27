"""The dormant Box-to-storm producer composition seam."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from squatch.box import Box
from squatch.daemon import compose_daemon_storm_producer
from squatch.journal import Journal, render_ts
from squatch.seams import LocalFilesystem
from squatch.storm import OccurrenceWindow, StormLedger


T0 = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self, now=T0):
        self.now = now

    def __call__(self):
        return self.now


def enqueue(box, detail="failure", *, stage="implement"):
    return box.enqueue(message_class="suggestion", summary=detail, detail=detail,
                       origin="producer", stage=stage)


def occurrences(journal):
    return [event for event in journal.read()
            if event.body.get("kind") == "storm_occurrence"]


def test_explicit_and_scoped_recorders_have_stable_arrival_identities(tmp_path):
    fs, clock = LocalFilesystem(), Clock()
    explicit_calls = []
    explicit = Box(tmp_path, fs=fs, clock=clock,
                   occurrence_recorder=lambda **values: explicit_calls.append(values))
    first = enqueue(explicit)
    second = enqueue(explicit)
    assert first.id == second.id and second.duplicate
    assert [call["occurrence_id"] for call in explicit_calls] == [f"{first.id}/1", f"{first.id}/2"]

    with Journal(tmp_path, clock=clock) as journal:
        scoped = Box(tmp_path, fs=fs, clock=clock)
        with compose_daemon_storm_producer(state_dir=tmp_path, journal=journal, fs=fs,
                                           clock=clock):
            third = enqueue(scoped)
            assert third.duplicate
            preferred = enqueue(explicit, "explicit preference")
            assert explicit_calls[-1]["occurrence_id"] == f"{preferred.id}/1"
        events = occurrences(journal)
        assert [(event.key, event.body) for event in events] == [
            (f"storm-occurrence/{scoped.get(first.id).signature}/{first.id}/1",
             {"kind": "storm_occurrence", "signature": scoped.get(first.id).signature,
              "occurrence_id": f"{first.id}/1", "emitting_stage": "implement"}),
            (f"storm-occurrence/{scoped.get(first.id).signature}/{first.id}/2",
             {"kind": "storm_occurrence", "signature": scoped.get(first.id).signature,
              "occurrence_id": f"{first.id}/2", "emitting_stage": "implement"}),
            (f"storm-occurrence/{scoped.get(first.id).signature}/{first.id}/3",
             {"kind": "storm_occurrence", "signature": scoped.get(first.id).signature,
              "occurrence_id": f"{first.id}/3", "emitting_stage": "implement"}),
        ]
        assert not StormLedger(journal=journal).record(
            signature=scoped.get(first.id).signature, occurrence_id=f"{first.id}/3",
            emitting_stage="implement")
        assert len(occurrences(journal)) == 3


@pytest.mark.asyncio
async def test_scope_is_synchronous_nested_and_task_context_is_caller_owned(tmp_path, monkeypatch):
    fs, clock = LocalFilesystem(), Clock()
    created = []
    original = asyncio.create_task

    def track(coro, *args, **kwargs):
        created.append(coro)
        return original(coro, *args, **kwargs)

    monkeypatch.setattr(asyncio, "create_task", track)

    async def arrive(box, detail):
        await asyncio.sleep(0)
        return enqueue(box, detail)

    with Journal(tmp_path, clock=clock) as first_journal, Journal(tmp_path / "other", clock=clock) as second_journal:
        box = Box(tmp_path, fs=fs, clock=clock)
        unrelated = Box(tmp_path / "other", fs=fs, clock=clock)
        with compose_daemon_storm_producer(state_dir=tmp_path, journal=first_journal, fs=fs,
                                           clock=clock):
            task = asyncio.create_task(arrive(box, "task arrival"))
            result = await task
            enqueue(unrelated, "unrelated")
            with compose_daemon_storm_producer(state_dir=tmp_path / "other",
                                               journal=second_journal, fs=fs, clock=clock):
                enqueue(unrelated, "nested")
            restored = enqueue(box, "restored")
        assert len(created) == 1
        assert [event.body["occurrence_id"] for event in occurrences(first_journal)] == [
            f"{result.id}/1", f"{restored.id}/1"]
        assert len(occurrences(second_journal)) == 2
        enqueue(box, "after exit")
        assert len(occurrences(first_journal)) == 2
        with pytest.raises(RuntimeError):
            with compose_daemon_storm_producer(state_dir=tmp_path, journal=first_journal,
                                               fs=fs, clock=clock):
                exceptional = asyncio.create_task(arrive(box, "unwind"))
                exceptional_result = await exceptional
                raise RuntimeError("unwind")
        assert len(created) == 2
        assert occurrences(first_journal)[-1].body["occurrence_id"] == (
            f"{exceptional_result.id}/1")
        enqueue(box, "after exceptional exit")
        assert len(occurrences(first_journal)) == 4


def test_write_precedes_recorder_and_failure_leaves_the_box_durable(tmp_path):
    fs, clock = LocalFilesystem(), Clock()
    queue = None

    def fail(**_values):
        assert queue is not None and queue.pending()
        raise RuntimeError("recorder failed")

    queue = Box(tmp_path, fs=fs, clock=clock, occurrence_recorder=fail)
    with pytest.raises(RuntimeError, match="recorder failed"):
        enqueue(queue)
    assert queue.get(queue.pending()[0].id).reports == 1


def test_failed_box_write_does_not_call_the_recorder(tmp_path):
    class FailingFilesystem:
        def write(self, _path, _data):
            raise OSError("disk full")

    calls = []
    queue = Box(tmp_path, fs=FailingFilesystem(), clock=Clock(),
                occurrence_recorder=lambda **values: calls.append(values))
    with pytest.raises(OSError, match="disk full"):
        enqueue(queue)
    assert calls == []


def test_reconciliation_is_ordered_idempotent_rolled_and_uses_append_time(tmp_path):
    fs, box_clock, journal_clock = LocalFilesystem(), Clock(), Clock()
    queue = Box(tmp_path, fs=fs, clock=box_clock)
    first = enqueue(queue, "same")
    enqueue(queue, "same")
    enqueue(queue, "same")
    resolved = enqueue(queue, "resolved", stage="triage")
    queue.resolve(resolved.id, status="decided", link="ticket", note="done")
    with Journal(tmp_path, clock=journal_clock) as journal:
        ledger = StormLedger(journal=journal)
        first_message = queue.get(first.id)
        assert ledger.record(signature=first_message.signature, occurrence_id=f"{first.id}/1",
                             emitting_stage="implement")
        old_ts = occurrences(journal)[0].ts
        journal_clock.now += timedelta(hours=25)
        journal.append("signal", {"kind": "unrelated"})
        reconcile_time = journal_clock.now
        with compose_daemon_storm_producer(state_dir=tmp_path, journal=journal, fs=fs,
                                           clock=box_clock):
            pass
        assert len(journal.segments()) == 2
        events = occurrences(journal)
        assert [event.body["occurrence_id"] for event in events] == [
            f"{first.id}/1", f"{first.id}/2", f"{first.id}/3", f"{resolved.id}/1"]
        assert events[0].ts == old_ts
        assert [event.ts for event in events[1:]] == [render_ts(reconcile_time)] * 3
        before = tuple(events)
        with compose_daemon_storm_producer(state_dir=tmp_path, journal=journal, fs=fs,
                                           clock=box_clock):
            pass
        assert tuple(occurrences(journal)) == before


def test_entry_failure_resets_the_binding(tmp_path, monkeypatch):
    fs, clock = LocalFilesystem(), Clock()
    queue = Box(tmp_path, fs=fs, clock=clock)
    enqueue(queue)
    with Journal(tmp_path, clock=clock) as journal:
        def fail(*_args, **_kwargs):
            raise RuntimeError("reconciliation failed")

        monkeypatch.setattr(StormLedger, "record", fail)
        with pytest.raises(RuntimeError, match="reconciliation failed"):
            with compose_daemon_storm_producer(state_dir=tmp_path, journal=journal, fs=fs,
                                               clock=clock):
                pass
        monkeypatch.undo()
        enqueue(queue, "after failed entry")
        assert occurrences(journal) == []


def test_producer_emits_one_trip_report_and_no_dispatch_hold(tmp_path):
    fs, clock = LocalFilesystem(), Clock()
    with Journal(tmp_path, clock=clock) as journal:
        queue = Box(tmp_path, fs=fs, clock=clock)
        with compose_daemon_storm_producer(state_dir=tmp_path, journal=journal, fs=fs,
                                           clock=clock):
            for _ in range(6):
                enqueue(queue, "storm")
        message = queue.pending()[0]
        window = StormLedger(journal=journal).window(now=clock.now)
        assert window == {message.signature: OccurrenceWindow(
            tuple(f"{message.id}/{n}" for n in range(1, 7)), 6, True)}
        assert {event.type for event in journal.read()} == {"signal"}
        assert {event.body["kind"] for event in journal.read()} == {
            "storm_occurrence", "storm_trip"}
        reports = [item for item in queue.pending()
                   if item.message_class == "failure_report"]
        assert len(reports) == 1 and reports[0].origin.startswith("storm-breaker:P0:")
        assert all(event.body.get("kind") != "control_hold" for event in journal.read())
