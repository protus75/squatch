"""The pause/resume CLI uses the lock holder as the only journal writer."""

import asyncio
import json
from datetime import timedelta
from io import StringIO
from uuid import UUID, uuid4

import pytest

from test_cli import STATE, T0, checkout, git_env  # noqa: F401

import squatch.__main__ as main_module
from squatch.__main__ import main
from squatch.daemon import DispatchPause
from squatch.control import ControlInbox, ControlRequest
from squatch.journal import Journal, read_events
from squatch.lockfile import LOCK_NAME, Lockfile
from squatch.seams import LocalFilesystem


def _holds(state):
    return [event.body for event in read_events(state)
            if event.type == "signal" and event.body.get("kind") == "control_hold"]


def _decision(state, request_id):
    return next(event.body for event in reversed(tuple(read_events(state)))
                if event.key == f"control/{request_id}")


def test_live_lock_publishes_without_writing_and_a_prehold_release_is_stale(checkout):
    state = checkout / STATE
    fs = LocalFilesystem()
    lock = Lockfile(state, instance_id="engine", clock=lambda: T0)
    lock.acquire()
    with Journal(state, clock=lambda: T0) as journal:
        inbox = ControlInbox(state, journal=journal, fs=fs)
        journal.append("signal", {"kind": "control_lifecycle", "lifecycle": str(inbox.lifecycle),
                                  "holder": json.loads(lock.path.read_text())})
    try:
        before = tuple(read_events(state))
        out = StringIO()
        assert main(["pause"], cwd=checkout, env=git_env(checkout.parent), out=out) == 0
        pause_request = ControlRequest.model_validate_json(
            next((state / "control").glob("*.json")).read_bytes())
        assert main(["resume", "--hold-id", str(pause_request.request_id)], cwd=checkout,
                    env=git_env(checkout.parent), out=out) == 0
        requests = list((state / "control").glob("*.json"))
        typed = [ControlRequest.model_validate_json(path.read_bytes()) for path in requests]
        release_request = next(request for request in typed if request.action == "release")
        assert {request.action for request in typed} == {"pause", "release"}
        assert tuple(read_events(state)) == before
        assert out.getvalue().splitlines() == [
            f"published pause: hold id {pause_request.request_id}",
            f"published resume: hold id {pause_request.request_id}"]
    finally:
        lock.release()

    with Journal(state, clock=lambda: T0) as journal:
        inbox = ControlInbox(
            state, journal=journal, fs=fs, lifecycle=pause_request.lifecycle)
        pause = DispatchPause(inbox)
        asyncio.run(inbox.consume(pause.apply))
        assert pause.hold_id == pause_request.request_id
    assert _decision(state, pause_request.request_id)["outcome"] == "accepted"
    assert _decision(state, release_request.request_id)["outcome"] == "stale"


def test_no_engine_pause_rehydrates_and_matching_resume_releases(checkout):
    state = checkout / STATE
    out = StringIO()
    assert main(["pause"], cwd=checkout, env=git_env(checkout.parent), out=out,
                clock=lambda: T0) == 0
    hold = next(body for body in _holds(state) if not body["released"])
    assert hold["hold_id"] in out.getvalue()
    out = StringIO()
    assert main(["resume", "--hold-id", hold["hold_id"]], cwd=checkout,
                env=git_env(checkout.parent), out=out, clock=lambda: T0) == 0
    assert out.getvalue() == f"applied resume: hold id {hold['hold_id']}\n"
    assert _holds(state)[-1]["released"] is True


def test_no_engine_stale_resume_refuses_and_preserves_the_current_hold(checkout):
    state = checkout / STATE
    env = git_env(checkout.parent)
    assert main(["pause"], cwd=checkout, env=env, out=StringIO(), clock=lambda: T0) == 0
    old_hold = _holds(state)[-1]["hold_id"]
    assert main(["resume", "--hold-id", old_hold], cwd=checkout, env=env,
                out=StringIO(), clock=lambda: T0) == 0
    assert main(["pause"], cwd=checkout, env=env, out=StringIO(), clock=lambda: T0) == 0
    active_hold = _holds(state)[-1]
    for stale_hold in (str(uuid4()), old_hold):
        out = StringIO()
        before = _holds(state)
        assert main(["resume", "--hold-id", stale_hold], cwd=checkout, env=env,
                    out=out, clock=lambda: T0) == 2
        assert "hold does not match" in out.getvalue()
        assert "paved road: check the active hold id" in out.getvalue()
        assert "applied" not in out.getvalue()
        assert _holds(state) == before
        with Journal(state, clock=lambda: T0) as journal:
            assert ControlInbox.active_lifecycle(journal) == UUID(active_hold["lifecycle"])
        decision = tuple(read_events(state))[-1].body
        assert decision["outcome"] == "stale"
        assert decision["request"]["hold_id"] == stale_hold


def test_cli_request_for_a_superseded_lifecycle_is_decided_stale(checkout, monkeypatch):
    state = checkout / STATE
    fs = LocalFilesystem()
    out = StringIO()
    old_lifecycle, current_lifecycle = uuid4(), uuid4()
    lock = Lockfile(state, instance_id="engine", clock=lambda: T0)
    lock.acquire()
    holder = json.loads(lock.path.read_text())
    with Journal(state, clock=lambda: T0) as journal:
        journal.append("signal", {"kind": "control_lifecycle", "lifecycle": str(old_lifecycle),
                                  "holder": holder})
        original_publish = main_module.publish_control

        def supersede(state_dir, request, filesystem):
            journal.append("signal", {"kind": "control_lifecycle",
                                      "lifecycle": str(current_lifecycle), "holder": holder})
            return original_publish(state_dir, request, filesystem)

        monkeypatch.setattr(main_module, "publish_control", supersede)
        try:
            assert main(["pause"], cwd=checkout, env=git_env(checkout.parent), out=out) == 0
        finally:
            lock.release()
        request = ControlRequest.model_validate_json(
            next((state / "control").glob("*.json")).read_bytes())
        assert request.lifecycle == old_lifecycle
        inbox = ControlInbox(state, journal=journal, fs=fs, lifecycle=current_lifecycle)
        asyncio.run(inbox.consume(lambda received: _never(received)))

    assert _decision(state, request.request_id)["outcome"] == "stale"
    assert not _holds(state)


def test_release_for_an_earlier_lifecycle_hold_does_not_release_the_current_hold(checkout):
    state = checkout / STATE
    out = StringIO()
    assert main(["pause"], cwd=checkout, env=git_env(checkout.parent), out=out,
                clock=lambda: T0) == 0
    old_hold = UUID(_holds(state)[-1]["hold_id"])
    assert main(["resume", "--hold-id", str(old_hold)], cwd=checkout,
                env=git_env(checkout.parent), out=out, clock=lambda: T0) == 0
    assert main(["pause"], cwd=checkout, env=git_env(checkout.parent), out=out,
                clock=lambda: T0) == 0
    current = next(body for body in reversed(_holds(state)) if not body["released"])
    lifecycle = UUID(current["lifecycle"])
    lock = Lockfile(state, instance_id="engine", clock=lambda: T0)
    lock.acquire()
    with Journal(state, clock=lambda: T0) as journal:
        journal.append("signal", {"kind": "control_lifecycle", "lifecycle": str(lifecycle),
                                  "holder": json.loads(lock.path.read_text())})
    try:
        assert main(["resume", "--hold-id", str(old_hold)], cwd=checkout,
                    env=git_env(checkout.parent), out=out, clock=lambda: T0) == 0
    finally:
        lock.release()
    path = next((state / "control").glob("*.json"))
    release = ControlRequest.model_validate_json(path.read_bytes())
    with Journal(state, clock=lambda: T0) as journal:
        inbox = ControlInbox(state, journal=journal, fs=LocalFilesystem(), lifecycle=lifecycle)
        inbox.rehydrate_holds()
        pause = DispatchPause(inbox)
        asyncio.run(inbox.consume(pause.apply))
        assert str(pause.hold_id) == current["hold_id"]
    assert _decision(state, release.request_id)["outcome"] == "stale"


async def _never(request):
    raise AssertionError(f"unexpected mutation: {request}")


@pytest.mark.parametrize("changed_field", ["pid", "started_at"])
def test_nonconsumer_with_same_version_as_previous_drain_is_refused(checkout, changed_field):
    state = checkout / STATE
    env = git_env(checkout.parent)
    assert main(["drain"], cwd=checkout, env=env, out=StringIO(), clock=lambda: T0) == 0
    previous = json.loads((state / LOCK_NAME).read_text())
    published = next(event.body for event in reversed(tuple(read_events(state)))
                     if event.body.get("kind") == "control_lifecycle")
    assert published["holder"] == previous

    # Each case changes just one acquisition field while retaining the engine
    # version, proving neither pid nor acquisition time can be ignored.
    now = T0 + timedelta(seconds=1) if changed_field == "started_at" else T0
    with Lockfile(state, instance_id=previous["instance_id"], clock=lambda: now) as lock:
        if changed_field == "pid":
            holder = json.loads(lock.path.read_text())
            holder["pid"] += 1
            lock.path.write_text(json.dumps(holder))
        before = tuple(read_events(state))
        out = StringIO()
        assert main(["pause"], cwd=checkout, env=env, out=out) == 2
        assert "not a live drain control consumer" in out.getvalue()
        assert "paved road:" in out.getvalue()
        assert tuple(read_events(state)) == before
        assert not tuple((state / "control").glob("*.json"))
