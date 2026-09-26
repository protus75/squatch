"""Durable, identity-bound control intake for the journal lock holder."""

from datetime import datetime, timezone
import os
from uuid import UUID, uuid4

import pytest

from squatch.control import ControlInbox, ControlRequest, publish_control
from squatch.journal import Journal
from squatch.seams import LocalFilesystem


NOW = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)


class IdempotentMutations:
    """A governed state projection keyed by the accepted request identity."""

    def __init__(self):
        self.applied: set[UUID] = set()
        self.calls = 0
        self.fail_after_apply = False

    async def __call__(self, request):
        self.calls += 1
        self.applied.add(request.request_id)
        if self.fail_after_apply:
            self.fail_after_apply = False
            raise RuntimeError("crash after governed mutation")


def signals(journal):
    return [event for event in journal.read()
            if event.type == "signal" and event.body.get("kind") == "control_decision"]


@pytest.mark.asyncio
async def test_decision_is_durable_before_governed_mutation(tmp_path):
    fs = LocalFilesystem()
    lifecycle = uuid4()
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        inbox = ControlInbox(tmp_path, journal=journal, fs=fs, lifecycle=lifecycle)
        request = ControlRequest(action="pause", lifecycle=lifecycle)
        publish_control(tmp_path, request, fs)

        async def mutate(received):
            event = signals(journal)[-1]
            assert event.body["outcome"] == "accepted"
            assert event.body["request"]["request_id"] == str(received.request_id)

        decisions = await inbox.consume(mutate)

    assert [decision.outcome for decision in decisions] == ["accepted"]
    assert not (tmp_path / "control" / f"{request.request_id}.json").exists()


@pytest.mark.asyncio
async def test_crash_after_decision_before_mutation_calls_mutation_once(tmp_path):
    fs = LocalFilesystem()
    lifecycle = uuid4()
    mutation = IdempotentMutations()
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        request = ControlRequest(action="pause", lifecycle=lifecycle)
        publish_control(tmp_path, request, fs)

        class CrashAfterAppend:
            crashed = False

            def append(self, *args, **kwargs):
                result = journal.append(*args, **kwargs)
                if not self.crashed:
                    self.crashed = True
                    raise RuntimeError("crash after decision")
                return result

            def read(self):
                return journal.read()

        crashing = ControlInbox(
            tmp_path, journal=CrashAfterAppend(), fs=fs, lifecycle=lifecycle)
        with pytest.raises(RuntimeError, match="crash after decision"):
            await crashing.consume(mutation)
        assert mutation.applied == set()

        replay = ControlInbox(tmp_path, journal=journal, fs=fs, lifecycle=lifecycle)
        await replay.consume(mutation)

    assert mutation.applied == {request.request_id} and mutation.calls == 1
    assert [event.body["applied"] for event in signals_from_path(tmp_path)] == [False, True]


@pytest.mark.asyncio
async def test_crash_after_mutation_returns_before_applied_append_retries_idempotently(tmp_path):
    fs = LocalFilesystem()
    lifecycle = uuid4()
    mutation = IdempotentMutations()
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        class CrashBeforeApplied:
            crashed = False

            def append(self, kind, body, **kwargs):
                if body.get("applied") and not self.crashed:
                    self.crashed = True
                    raise RuntimeError("crash before applied append")
                return journal.append(kind, body, **kwargs)

            def read(self):
                return journal.read()

        inbox = ControlInbox(
            tmp_path, journal=CrashBeforeApplied(), fs=fs, lifecycle=lifecycle)
        request = ControlRequest(action="kill", lifecycle=lifecycle)
        publish_control(tmp_path, request, fs)

        with pytest.raises(RuntimeError, match="crash before applied append"):
            await inbox.consume(mutation)
        assert mutation.calls == 1
        assert [event.body["applied"] for event in signals(journal)] == [False]
        assert (tmp_path / "control" / f"{request.request_id}.json").exists()
        await inbox.consume(mutation)

        assert [event.body["applied"] for event in signals(journal)] == [False, True]
    assert mutation.applied == {request.request_id} and mutation.calls == 2


@pytest.mark.parametrize("boundary", ["after_applied_append", "before_remove"])
@pytest.mark.asyncio
async def test_crash_after_applied_marker_never_repeats_mutation(tmp_path, boundary):
    fs = LocalFilesystem()
    lifecycle = uuid4()
    mutation = IdempotentMutations()
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        class CrashAfterApplied:
            def append(self, kind, body, **kwargs):
                result = journal.append(kind, body, **kwargs)
                if body.get("applied"):
                    raise RuntimeError("crash after applied append")
                return result

            def read(self):
                return journal.read()

        class CrashBeforeRemove(LocalFilesystem):
            def remove(self, path):
                raise RuntimeError("crash before removal")

        inbox = ControlInbox(
            tmp_path, lifecycle=lifecycle,
            journal=CrashAfterApplied() if boundary == "after_applied_append" else journal,
            fs=CrashBeforeRemove() if boundary == "before_remove" else fs)
        request = ControlRequest(action="pause", lifecycle=lifecycle)
        path = publish_control(tmp_path, request, fs)
        with pytest.raises(RuntimeError, match="crash"):
            await inbox.consume(mutation)
        assert path.exists() and mutation.calls == 1

    with Journal(tmp_path, clock=lambda: NOW) as journal:
        replay = ControlInbox(tmp_path, journal=journal, fs=fs, lifecycle=lifecycle)
        await replay.consume(mutation)
        assert [event.body["applied"] for event in signals(journal)] == [False, True]
    assert not path.exists() and mutation.calls == 1


@pytest.mark.parametrize("action", ["pause", "kill"])
@pytest.mark.asyncio
async def test_completed_request_republication_never_repeats_mutation(tmp_path, action):
    fs = LocalFilesystem()
    mutation = IdempotentMutations()
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        inbox = ControlInbox(tmp_path, journal=journal, fs=fs)
        request = ControlRequest(action=action, lifecycle=inbox.lifecycle)
        publish_control(tmp_path, request, fs)
        await inbox.consume(mutation)
        for _ in range(2):
            path = publish_control(tmp_path, request, fs)
            decisions = await inbox.consume(mutation)
            assert decisions[0].applied and not path.exists()
        assert len(signals(journal)) == 2
    assert mutation.calls == 1


@pytest.mark.asyncio
async def test_crash_after_removal_does_not_redeliver(tmp_path):
    lifecycle = uuid4()
    mutation = IdempotentMutations()
    local = LocalFilesystem()

    class CrashAfterRemove(LocalFilesystem):
        crashed = False

        def remove(self, path):
            super().remove(path)
            if not self.crashed:
                self.crashed = True
                raise RuntimeError("crash after removal")

    with Journal(tmp_path, clock=lambda: NOW) as journal:
        request = ControlRequest(action="pause", lifecycle=lifecycle)
        publish_control(tmp_path, request, local)
        inbox = ControlInbox(
            tmp_path, journal=journal, fs=CrashAfterRemove(), lifecycle=lifecycle)
        with pytest.raises(RuntimeError, match="crash after removal"):
            await inbox.consume(mutation)
        await ControlInbox(
            tmp_path, journal=journal, fs=local, lifecycle=lifecycle).consume(mutation)

    assert mutation.applied == {request.request_id} and mutation.calls == 1


@pytest.mark.asyncio
async def test_restart_has_new_identity_and_terminals_an_old_acceptance(tmp_path):
    fs = LocalFilesystem()
    first_mutation = IdempotentMutations()
    first_mutation.fail_after_apply = True
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        first = ControlInbox(tmp_path, journal=journal, fs=fs)
        request = ControlRequest(action="pause", lifecycle=first.lifecycle)
        publish_control(tmp_path, request, fs)
        with pytest.raises(RuntimeError):
            await first.consume(first_mutation)

    second_mutation = IdempotentMutations()
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        restarted = ControlInbox(tmp_path, journal=journal, fs=fs)
        assert restarted.lifecycle != first.lifecycle
        decisions = await restarted.consume(second_mutation)
        assert [event.body["outcome"] for event in signals(journal)] == [
            "accepted", "stale"]

    assert [decision.outcome for decision in decisions] == ["stale"]
    assert second_mutation.applied == set()


@pytest.mark.asyncio
async def test_stale_lifecycle_and_pre_hold_release_never_mutate(tmp_path):
    fs = LocalFilesystem()
    lifecycle = uuid4()
    mutation = IdempotentMutations()
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        inbox = ControlInbox(tmp_path, journal=journal, fs=fs, lifecycle=lifecycle)
        stale = ControlRequest(action="kill", lifecycle=uuid4())
        premature = ControlRequest(
            action="release", lifecycle=lifecycle, hold_id=uuid4())
        publish_control(tmp_path, stale, fs)
        publish_control(tmp_path, premature, fs)
        later_hold = inbox.hold()
        decisions = await inbox.consume(mutation)

    assert [decision.outcome for decision in decisions] == ["stale", "stale"]
    assert mutation.applied == set()
    assert later_hold in inbox.holds and later_hold != premature.hold_id


@pytest.mark.asyncio
async def test_release_is_bound_to_one_never_reused_hold_instance(tmp_path):
    fs = LocalFilesystem()
    lifecycle = uuid4()
    mutation = IdempotentMutations()
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        inbox = ControlInbox(tmp_path, journal=journal, fs=fs, lifecycle=lifecycle)
        first_hold = inbox.hold()
        release = ControlRequest(
            action="release", lifecycle=lifecycle, hold_id=first_hold)
        publish_control(tmp_path, release, fs)
        await inbox.consume(mutation)
        second_hold = inbox.hold()

        publish_control(tmp_path, release, fs)
        await inbox.consume(mutation)

    assert first_hold not in inbox.holds and second_hold in inbox.holds
    assert first_hold != second_hold
    assert mutation.applied == {release.request_id} and mutation.calls == 1


@pytest.mark.asyncio
async def test_reused_request_id_with_different_request_is_conflict(tmp_path):
    fs = LocalFilesystem()
    lifecycle = uuid4()
    mutation = IdempotentMutations()
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        inbox = ControlInbox(tmp_path, journal=journal, fs=fs, lifecycle=lifecycle)
        first = ControlRequest(action="pause", lifecycle=lifecycle)
        publish_control(tmp_path, first, fs)
        await inbox.consume(mutation)
        conflicting = first.model_copy(update={"action": "kill"})
        publish_control(tmp_path, conflicting, fs)
        decisions = await inbox.consume(mutation)

    assert [decision.outcome for decision in decisions] == ["conflict"]
    assert mutation.applied == {first.request_id} and mutation.calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("previous", ["accepted", "stale", "invalid", "conflict"])
@pytest.mark.parametrize("remove_crashes", [0, 2])
async def test_changed_request_after_decision_is_journaled_conflict(
        tmp_path, monkeypatch, previous, remove_crashes):
    fs = LocalFilesystem()
    mutation = IdempotentMutations()
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        inbox = ControlInbox(tmp_path, journal=journal, fs=fs)
        hold = inbox.hold()
        first = ControlRequest(
            action="pause", lifecycle=inbox.lifecycle if previous == "accepted" else uuid4())
        path = tmp_path / "control" / f"{first.request_id}.json"
        if previous == "invalid":
            fs.publish(path, b"not json")
        else:
            publish_control(tmp_path, first, fs)
        await inbox.consume(mutation)
        if previous == "conflict":
            publish_control(tmp_path, first.model_copy(update={"action": "kill"}), fs)
            await inbox.consume(mutation)
        assert signals(journal)[-1].body["outcome"] == previous
        before = len(signals(journal))
        mutation_calls = mutation.calls

        replacement = ControlRequest(request_id=first.request_id, action="release",
                                     lifecycle=inbox.lifecycle, hold_id=hold)
        publish_control(tmp_path, replacement, fs)

        def interrupted_remove(received):
            raise RuntimeError("crash before removal")

        with monkeypatch.context() as patch:
            patch.setattr(fs, "remove", interrupted_remove)
            for _ in range(remove_crashes):
                with pytest.raises(RuntimeError, match="crash before removal"):
                    await inbox.consume(mutation)
                assert len(signals(journal)) == before + 1
                assert path.exists()
                assert mutation.calls == mutation_calls and inbox.holds == {hold}
        decisions = await inbox.consume(mutation)

        assert [decision.outcome for decision in decisions] == ["conflict"]
        assert len(signals(journal)) == before + 1
        event = signals(journal)[-1]
        assert event.key == f"control/{first.request_id}"
        assert event.body["outcome"] == "conflict"
        assert event.body["request"] == replacement.model_dump(mode="json")
        assert mutation.calls == mutation_calls and inbox.holds == {hold}
        assert not path.exists()

        publish_control(tmp_path, replacement, fs)
        assert await inbox.consume(mutation) == decisions
        assert len(signals(journal)) == before + 1
        assert mutation.calls == mutation_calls and inbox.holds == {hold}
        assert not path.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_data", [
    b"not json",
    b'{"action":"unknown"}',
    b'{"action":"pause","lifecycle":"00000000-0000-0000-0000-000000000001",'
    b'"extra":true}',
    b'{"action":"release","lifecycle":"00000000-0000-0000-0000-000000000001"}',
])
async def test_malformed_request_is_journaled_and_does_not_stop_the_pass(tmp_path, bad_data):
    fs = LocalFilesystem()
    lifecycle = uuid4()
    mutation = IdempotentMutations()
    control = tmp_path / "control"
    control.mkdir()
    bad = control / "00000000-0000-0000-0000-000000000000.json"
    fs.publish(bad, bad_data)
    good = ControlRequest(action="pause", lifecycle=lifecycle)
    publish_control(tmp_path, good, fs)

    with Journal(tmp_path, clock=lambda: NOW) as journal:
        inbox = ControlInbox(tmp_path, journal=journal, fs=fs, lifecycle=lifecycle)
        decisions = await inbox.consume(mutation)

    assert [decision.outcome for decision in decisions] == ["invalid", "accepted"]
    assert mutation.applied == {good.request_id}


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", ["malformed", "filename_mismatch", "missing_request_id"])
async def test_terminal_invalid_decision_is_not_duplicated_after_remove_crash(tmp_path, payload):
    local = LocalFilesystem()
    lifecycle = uuid4()
    request = ControlRequest(action="pause", lifecycle=lifecycle)
    path = tmp_path / "control" / f"{uuid4()}.json"
    content = {
        "malformed": b"not json",
        "filename_mismatch": request.model_dump_json().encode(),
        "missing_request_id": request.model_dump_json(exclude={"request_id"}).encode(),
    }[payload]
    local.publish(path, content)
    mutation = IdempotentMutations()

    class CrashBeforeRemove(LocalFilesystem):
        def remove(self, received):
            raise RuntimeError("crash before removal")

    for _ in range(2):
        with Journal(tmp_path, clock=lambda: NOW) as journal:
            inbox = ControlInbox(
                tmp_path, journal=journal, fs=CrashBeforeRemove(), lifecycle=lifecycle)
            with pytest.raises(RuntimeError, match="crash before removal"):
                await inbox.consume(mutation)
            assert path.read_bytes() == content
            events = signals(journal)
            assert [event.body["outcome"] for event in events] == ["invalid"]
            assert events[0].key == f"control/{path.stem}"
            assert mutation.calls == 0

    with Journal(tmp_path, clock=lambda: NOW) as journal:
        inbox = ControlInbox(tmp_path, journal=journal, fs=local, lifecycle=lifecycle)
        decisions = await inbox.consume(mutation)
        assert [decision.outcome for decision in decisions] == ["invalid"]
        assert signals(journal) == events
        assert await inbox.consume(mutation) == ()

    assert not path.exists() and mutation.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", [
    "lifecycle does not match", "hold does not match", "accepted lifecycle ended",
])
async def test_stale_decision_is_not_duplicated_after_remove_crash(tmp_path, reason):
    local = LocalFilesystem()
    lifecycle = uuid4()
    request = (ControlRequest(action="release", lifecycle=lifecycle, hold_id=uuid4())
               if reason == "hold does not match" else
               ControlRequest(action="kill", lifecycle=uuid4()))
    path = publish_control(tmp_path, request, local)
    if reason == "accepted lifecycle ended":
        with Journal(tmp_path, clock=lambda: NOW) as journal:
            original = ControlInbox(
                tmp_path, journal=journal, fs=local, lifecycle=request.lifecycle)

            async def interrupted_mutation(received):
                raise RuntimeError("crash before mutation")

            with pytest.raises(RuntimeError, match="crash before mutation"):
                await original.consume(interrupted_mutation)

    class CrashBeforeRemove(LocalFilesystem):
        def remove(self, received):
            raise RuntimeError("crash before removal")

    mutation = IdempotentMutations()
    for _ in range(2):
        with Journal(tmp_path, clock=lambda: NOW) as journal:
            inbox = ControlInbox(
                tmp_path, journal=journal, fs=CrashBeforeRemove(), lifecycle=lifecycle)
            hold = inbox.hold()
            with pytest.raises(RuntimeError, match="crash before removal"):
                await inbox.consume(mutation)
            events = signals(journal)
            expected = (["accepted", "stale"] if reason == "accepted lifecycle ended"
                        else ["stale"])
            assert [event.body["outcome"] for event in events] == expected
            assert events[-1].key == f"control/{request.request_id}"
            assert events[-1].body["reason"] == reason
            assert path.exists() and inbox.holds == {hold} and mutation.calls == 0

    with Journal(tmp_path, clock=lambda: NOW) as journal:
        inbox = ControlInbox(tmp_path, journal=journal, fs=local, lifecycle=lifecycle)
        decisions = await inbox.consume(mutation)
        assert [decision.outcome for decision in decisions] == ["stale"]
        assert signals(journal) == events

    assert not path.exists() and mutation.calls == 0


@pytest.mark.asyncio
async def test_changed_invalid_payload_is_read_and_journaled(tmp_path):
    fs = LocalFilesystem()
    path = tmp_path / "control" / "broken.json"
    mutation = IdempotentMutations()
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        inbox = ControlInbox(tmp_path, journal=journal, fs=fs)
        for content in (b"not json", b"different invalid json"):
            fs.publish(path, content)
            await inbox.consume(mutation)
        events = signals(journal)
        assert [event.body["outcome"] for event in events] == ["invalid", "invalid"]
        assert events[0].body["invalid_digest"] != events[1].body["invalid_digest"]
        assert mutation.calls == 0 and not path.exists()


@pytest.mark.asyncio
async def test_read_error_propagates_without_deleting_a_valid_request(tmp_path):
    lifecycle = uuid4()
    local = LocalFilesystem()
    request = ControlRequest(action="pause", lifecycle=lifecycle)
    path = publish_control(tmp_path, request, local)

    class ReadFailure(LocalFilesystem):
        def read(self, received):
            raise OSError("transient read failure")

    with Journal(tmp_path, clock=lambda: NOW) as journal:
        inbox = ControlInbox(
            tmp_path, journal=journal, fs=ReadFailure(), lifecycle=lifecycle)
        with pytest.raises(OSError, match="transient read failure"):
            await inbox.consume(IdempotentMutations())
        assert not signals(journal)

    assert path.exists()


@pytest.mark.asyncio
async def test_interrupted_real_publication_leaves_nothing_to_consume(
        tmp_path, monkeypatch):
    fs = LocalFilesystem()
    lifecycle = uuid4()
    request = ControlRequest(action="pause", lifecycle=lifecycle)

    def interrupted_link(src, dst):
        raise OSError("crash before publish")

    with monkeypatch.context() as patch:
        patch.setattr(os, "link", interrupted_link)
        with pytest.raises(OSError, match="crash before publish"):
            publish_control(tmp_path, request, fs)
    assert list((tmp_path / "control").iterdir()) == []

    mutation = IdempotentMutations()
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        inbox = ControlInbox(tmp_path, journal=journal, fs=fs, lifecycle=lifecycle)
        assert await inbox.consume(mutation) == ()
        assert not signals(journal)
        publish_control(tmp_path, request, fs)
        await inbox.consume(mutation)
        assert mutation.calls == 1


@pytest.mark.asyncio
async def test_abandoned_partial_temp_is_never_consumed(tmp_path):
    fs = LocalFilesystem()
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        inbox = ControlInbox(tmp_path, journal=journal, fs=fs)
        request = ControlRequest(action="pause", lifecycle=inbox.lifecycle)
        directory = tmp_path / "control"
        directory.mkdir()
        partial = directory / f".{request.request_id}.json.tmp"
        partial.write_bytes(b'{"action":')
        mutation = IdempotentMutations()
        assert await inbox.consume(mutation) == ()
        assert not signals(journal)
        publish_control(tmp_path, request, fs)
        await inbox.consume(mutation)
        assert mutation.calls == 1 and partial.exists()


def test_publication_needs_no_journal_and_refuses_overwrite(tmp_path):
    fs = LocalFilesystem()
    request = ControlRequest(action="pause", lifecycle=uuid4())
    path = publish_control(tmp_path, request, fs)
    original = path.read_bytes()

    with pytest.raises(FileExistsError):
        publish_control(tmp_path, request.model_copy(update={"action": "kill"}), fs)

    assert path.read_bytes() == original
    assert sorted(item.name for item in path.parent.iterdir()) == [path.name]


def signals_from_path(state_dir):
    with Journal(state_dir, clock=lambda: NOW) as journal:
        return signals(journal)
