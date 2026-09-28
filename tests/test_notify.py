"""Durable notification identities and conservative delivery recovery."""

import sys
from uuid import uuid4

import pytest

from squatch.effects import effect_key
from squatch.journal import Journal
from squatch.notify import NotificationReconciler
from squatch.seams import ExecutableNotFound, SubprocessNotifications
from squatch.storm import StormLedger
from test_cli import T0


class RecordingNotifications:
    def __init__(self):
        self.calls = []

    async def notify(self, argv):
        self.calls.append(list(argv))


def storm(journal, *, origin="candidate", signature="broken"):
    ledger = StormLedger(journal=journal)
    for index in range(6):
        ledger.record(signature=signature, occurrence_id=f"{signature}-{index}",
                      emitting_stage="check", emitting_origin=origin)
    crossing = next(c for c in ledger.crossings() if c["signature"] == signature)
    ledger.trip(crossing)
    return crossing["trip_id"]


def hold(journal, *, trigger="integration_red_streak", ticket="candidate", trip_id=None):
    identity = str(uuid4())
    body = dict(kind="control_hold", hold_id=identity, lifecycle=str(uuid4()),
                released=False, trigger=trigger)
    if trip_id is not None:
        body.update(trip_id=trip_id, stem=ticket)
    else:
        body.update(stems=[ticket], run_seq=0)
    journal.append("signal", body, ticket=ticket)
    return identity


def reconciler(journal, notifications, report):
    return NotificationReconciler(journal=journal, notifications=notifications,
                                  argv=["notify", "literal ; $argument"], report=report)


@pytest.mark.parametrize("origin", ["candidate", "finished", "box/source", None])
async def test_trip_without_hold_is_delivered_and_later_hold_does_not_resend(tmp_path, origin):
    notifications, reports = RecordingNotifications(), []
    with Journal(tmp_path, clock=lambda: T0) as journal:
        trip = storm(journal, origin=origin)
        notify = reconciler(journal, notifications, reports.append)
        await notify.reconcile()
        [argv] = notifications.calls
        assert argv[:2] == ["notify", "literal ; $argument"]
        assert f"storm-breaker trip: {trip}" in argv[-1]
        assert "No active hold exists" in argv[-1]
        assert f"control_hold with trip_id {trip}" in argv[-1]
        assert "run squatch resume with that record's --hold-id" in argv[-1]
        hold(journal, trigger="storm_trip", trip_id=trip, ticket=origin)
        await notify.reconcile()
        assert notifications.calls == [argv]
        assert reports == [argv[-1]]


async def test_keys_replay_and_new_signals_on_the_same_instance(tmp_path):
    notifications, reports = RecordingNotifications(), []
    with Journal(tmp_path, clock=lambda: T0) as journal:
        red = hold(journal)
        notify = reconciler(journal, notifications, reports.append)
        await notify.reconcile()
        trip = storm(journal)
        storm_hold = hold(journal, trigger="storm_trip", trip_id=trip)
        later_red = hold(journal)
        await notify.reconcile()
        assert len(notifications.calls) == 3
        for identity in (red, storm_hold, later_red):
            assert sum(f"squatch resume --hold-id {identity}" in argv[-1]
                       for argv in notifications.calls) == 1
        expected = {
            effect_key("notify", "candidate", "storm_trip", trip),
            effect_key("notify", "candidate", "integration_red_streak", red),
            effect_key("notify", "candidate", "integration_red_streak", later_red)}
        completions = [e for e in journal.read() if e.type == "effect_completion"]
        assert len(completions) == 3
        assert {e.key for e in completions} == expected
        assert {e.ticket for e in completions} == {"candidate"}
        journal.append("state_transition", {"to": "gate_failed"}, ticket="candidate")
        reports.clear()
        await notify.reconcile()
    with Journal(tmp_path, clock=lambda: T0) as journal:
        await reconciler(journal, notifications, reports.append).reconcile()
        assert len(notifications.calls) == 3
        assert reports == []


async def test_unmatched_intent_resends_after_restart(tmp_path):
    with Journal(tmp_path, clock=lambda: T0) as journal:
        identity = hold(journal)
        key = effect_key("notify", "candidate", "integration_red_streak", identity)
        journal.append("effect_intent", {}, key=key, ticket="candidate")
    notifications = RecordingNotifications()
    with Journal(tmp_path, clock=lambda: T0) as journal:
        notify = reconciler(journal, notifications, lambda line: None)
        await notify.reconcile()
        await notify.reconcile()
        assert len(notifications.calls) == 1
        assert [e.type for e in journal.read() if e.key == key] == [
            "effect_intent", "effect_intent", "effect_completion"]


@pytest.mark.parametrize("trigger", ["integration_red_streak", "storm_trip"])
@pytest.mark.parametrize("after_startup", [False, True])
@pytest.mark.parametrize("unmatched_intent", [False, True])
async def test_released_escalations_do_not_notify(
        tmp_path, trigger, after_startup, unmatched_intent):
    notifications, reports = RecordingNotifications(), []
    with Journal(tmp_path, clock=lambda: T0) as journal:
        notify = reconciler(journal, notifications, reports.append)
        if after_startup:
            await notify.reconcile()
        trip = storm(journal) if trigger == "storm_trip" else None
        identity = hold(journal, trigger=trigger, trip_id=trip)
        if unmatched_intent:
            journal.append("effect_intent", {}, ticket="candidate",
                           key=effect_key("notify", "candidate", trigger, trip or identity))
        held = next(e.body for e in journal.read() if e.body.get("hold_id") == identity)
        # ControlInbox releases name only the hold, not its trigger or trip.
        journal.append("signal", {"kind": "control_hold", "hold_id": identity,
                                  "lifecycle": held["lifecycle"], "released": True})
        before = tuple(journal.read())
        if not after_startup:
            notify = reconciler(journal, notifications, reports.append)

        await notify.reconcile()
        await notify.reconcile()

        assert notifications.calls == []
        assert reports == []
        assert tuple(journal.read()) == before


@pytest.mark.parametrize("error", [ExecutableNotFound("missing"), RuntimeError("exit 3"),
                                  TimeoutError()])
async def test_failure_reports_keeps_intent_and_continues_then_retries(tmp_path, error):
    notifications, reports = RecordingNotifications(), []
    original = notifications.notify
    calls = 0

    async def fail_once(argv):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise error
        await original(argv)

    notifications.notify = fail_once
    with Journal(tmp_path, clock=lambda: T0) as journal:
        first, second = hold(journal), hold(journal)
        notify = reconciler(journal, notifications, reports.append)
        await notify.reconcile()
        assert len(notifications.calls) == 1
        assert second in notifications.calls[0][-1]
        assert "notification failed" in reports[0]
        assert not any(e.type == "effect_completion" and first in e.key
                       for e in journal.read())
        await notify.reconcile()
        assert len(notifications.calls) == 2
        assert first in notifications.calls[-1][-1]


@pytest.mark.parametrize("failure", ["missing", "exit", "permission", "timeout"])
async def test_real_transport_failures_leave_only_intent(tmp_path, failure):
    argv = [str(tmp_path / "missing")]
    if failure == "permission":
        path = tmp_path / "not-executable"
        path.write_text("not executable")
        path.chmod(0o600)
        argv = [str(path)]
    elif failure == "exit":
        argv = [sys.executable, "-c", "raise SystemExit(7)"]
    elif failure == "timeout":
        argv = [sys.executable, "-c", "import time; time.sleep(60)"]
    reports = []
    with Journal(tmp_path, clock=lambda: T0) as journal:
        hold(journal)
        notify = NotificationReconciler(
            journal=journal, argv=argv, report=reports.append,
            notifications=SubprocessNotifications(cwd=tmp_path, env={}, timeout=.1))
        await notify.reconcile()
        assert len(reports) == 1 and "notification failed" in reports[0]
        assert [e.type for e in journal.read() if e.type.startswith("effect_")] == [
            "effect_intent"]


async def test_unrelated_signals_and_hold_release_do_not_notify(tmp_path):
    notifications = RecordingNotifications()
    with Journal(tmp_path, clock=lambda: T0) as journal:
        hold(journal, trigger="tree_hash_mismatch")
        journal.append("signal", {"kind": "watchdog"}, ticket="candidate")
        journal.append("signal", {"kind": "control_hold", "released": True,
                                  "hold_id": str(uuid4())})
        await reconciler(journal, notifications, lambda line: None).reconcile()
        assert notifications.calls == []

        for seq in (0, 1):
            for spiral in ("spend_without_progress", "stuck"):
                journal.append("signal", {"kind": "watchdog", "ticket": "candidate",
                                          "spiral": spiral, "run_seq": seq}, ticket="candidate")
        await reconciler(journal, notifications, lambda line: None).reconcile()
        assert len(notifications.calls) == 3
        assert sum("spend_without_progress" in c[-1] for c in notifications.calls) == 2
        assert sum("stuck" in c[-1] for c in notifications.calls) == 1
    with Journal(tmp_path, clock=lambda: T0) as journal:
        await reconciler(journal, notifications, lambda line: None).reconcile()
        assert len(notifications.calls) == 3


@pytest.mark.parametrize("spiral", ["spend_without_progress", "stuck"])
async def test_watchdog_unmatched_intent_retries_after_restart(tmp_path, spiral):
    notifications, reports = RecordingNotifications(), []
    original = notifications.notify

    async def broken(argv):
        raise RuntimeError("not delivered")

    notifications.notify = broken
    with Journal(tmp_path, clock=lambda: T0) as journal:
        journal.append("signal", {"kind": "watchdog", "ticket": "candidate",
                                  "spiral": spiral, "run_seq": 7}, ticket="candidate")
        await reconciler(journal, notifications, reports.append).reconcile()
        assert len(reports) == 1 and "notification failed" in reports[0]
        assert not any(e.type == "effect_completion" for e in journal.read())
    notifications.notify = original
    with Journal(tmp_path, clock=lambda: T0) as journal:
        await reconciler(journal, notifications, reports.append).reconcile()
        await reconciler(journal, notifications, reports.append).reconcile()
        assert len(notifications.calls) == 1
        assert [e.type for e in journal.read() if e.key and e.key.startswith("notify/")] == [
            "effect_intent", "effect_intent", "effect_completion"]
