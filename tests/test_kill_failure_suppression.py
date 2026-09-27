"""The serve kill boundary suppresses only its own worker cancellations."""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from squatch.control import ControlRequest, publish_control
from squatch.daemon import DaemonTasks, compose_daemon_control, kill_worker_stop_consumer
from squatch.journal import Journal
from squatch.seams import LocalFilesystem
from squatch.serve import ServeGraph


NOW = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)


class ActiveDriver:
    def __init__(self) -> None:
        self.aborts = 0

    async def abort_active(self) -> None:
        self.aborts += 1


def blocked(started: asyncio.Event, cancelled: asyncio.Event, starts: list[str], name: str):
    async def consume() -> None:
        starts.append(name)
        started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    return consume


def owner_for(inbox, active: ActiveDriver, started, cancelled, starts) -> DaemonTasks:
    owner: DaemonTasks

    async def control() -> None:
        await kill_worker_stop_consumer(inbox, active, owner)()

    owner = DaemonTasks(
        watcher=blocked(started[0], cancelled[0], starts, "watcher"),
        merge=blocked(started[1], cancelled[1], starts, "merge"),
        box=blocked(started[2], cancelled[2], starts, "box"), control=control)
    return owner


def decision(journal: Journal, request: ControlRequest, outcome: str) -> bool:
    return any(event.body.get("kind") == "control_decision"
               and event.body.get("request") == request.model_dump(mode="json")
               and event.body.get("outcome") == outcome for event in journal.read())


@pytest.mark.asyncio
async def test_current_kill_suppresses_only_its_observed_worker_cancellations(tmp_path):
    fs = LocalFilesystem()
    active = ActiveDriver()
    started = [asyncio.Event() for _ in range(3)]
    cancelled = [asyncio.Event() for _ in range(3)]
    starts: list[str] = []
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        inbox = compose_daemon_control(state_dir=tmp_path, journal=journal, fs=fs)
        owner = owner_for(inbox, active, started, cancelled, starts)
        run = asyncio.create_task(owner.run())
        await asyncio.gather(*(event.wait() for event in started))
        request = ControlRequest(action="kill", lifecycle=inbox.lifecycle)
        publish_control(tmp_path, request, fs)

        await asyncio.gather(*(event.wait() for event in cancelled))
        assert not run.done()
        assert starts == ["watcher", "merge", "box"]
        while not decision(journal, request, "accepted"):
            await asyncio.sleep(0)
        assert all(task.done() for task in owner._workers)
        assert starts == ["watcher", "merge", "box"]

        run.cancel()
        with pytest.raises(asyncio.CancelledError):
            await run


@pytest.mark.asyncio
async def test_stale_kill_does_not_suppress_an_independent_worker_failure(tmp_path):
    fs = LocalFilesystem()
    active = ActiveDriver()
    started = [asyncio.Event() for _ in range(3)]
    fail = asyncio.Event()
    cancelled = [asyncio.Event() for _ in range(2)]

    async def failing_worker() -> None:
        started[0].set()
        await fail.wait()
        raise RuntimeError("worker failed")

    owner: DaemonTasks
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        inbox = compose_daemon_control(state_dir=tmp_path, journal=journal, fs=fs)

        async def control() -> None:
            await kill_worker_stop_consumer(inbox, active, owner)()

        owner = DaemonTasks(
            watcher=failing_worker,
            merge=blocked(started[1], cancelled[0], [], "merge"),
            box=blocked(started[2], cancelled[1], [], "box"), control=control)
        stale = ControlRequest(action="kill", lifecycle=uuid4())
        publish_control(tmp_path, stale, fs)
        run = asyncio.create_task(owner.run())
        await asyncio.gather(*(event.wait() for event in started))
        while not decision(journal, stale, "stale"):
            await asyncio.sleep(0)
        assert active.aborts == 0
        assert not owner._kill_stopping
        assert all(not task.done() for task in owner._workers)
        assert not any(event.is_set() for event in cancelled)

        fail.set()
        with pytest.raises(RuntimeError, match="worker failed"):
            await run


@pytest.mark.asyncio
async def test_external_control_cancellation_propagates_after_a_current_kill(tmp_path):
    fs = LocalFilesystem()
    active = ActiveDriver()
    started = [asyncio.Event() for _ in range(3)]
    cancelled = [asyncio.Event() for _ in range(3)]
    starts: list[str] = []
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        inbox = compose_daemon_control(state_dir=tmp_path, journal=journal, fs=fs)
        owner = owner_for(inbox, active, started, cancelled, starts)
        run = asyncio.create_task(owner.run())
        await asyncio.gather(*(event.wait() for event in started))
        request = ControlRequest(action="kill", lifecycle=inbox.lifecycle)
        publish_control(tmp_path, request, fs)
        await asyncio.gather(*(event.wait() for event in cancelled))
        while not decision(journal, request, "accepted"):
            await asyncio.sleep(0)

        assert owner._control is not None
        owner._control.cancel()
        with pytest.raises(asyncio.CancelledError):
            await run


@pytest.mark.asyncio
async def test_serve_owner_never_suppresses_an_independent_terminal_worker_failure():
    started = asyncio.Event()
    failure = RuntimeError("production worker failed")

    async def watcher():
        started.set()
        raise failure

    owner = DaemonTasks(
        watcher=watcher,
        merge=blocked(asyncio.Event(), asyncio.Event(), [], "merge"),
        box=blocked(asyncio.Event(), asyncio.Event(), [], "box"),
        control=blocked(asyncio.Event(), asyncio.Event(), [], "control"))
    graph = ServeGraph(
        dispatch=None, pipeline=None, rework=None, triage=None, control=None,
        checkpoint=None, heartbeat=None, tasks=owner, stopped=asyncio.Event())

    with pytest.raises(RuntimeError, match="production worker failed"):
        await graph.run()
    assert started.is_set()
