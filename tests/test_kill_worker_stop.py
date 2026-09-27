"""The dormant kill boundary that stops only daemon worker siblings."""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from squatch.control import ControlRequest, publish_control
from squatch.daemon import DaemonTasks, compose_daemon_control, kill_worker_stop_consumer
from squatch.journal import Journal
from squatch.seams import LocalFilesystem


NOW = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)


class ActiveDriver:
    def __init__(self) -> None:
        self.aborting = asyncio.Event()
        self.unwind = asyncio.Event()
        self.aborts = 0

    async def abort_active(self) -> None:
        self.aborts += 1
        self.aborting.set()
        await self.unwind.wait()


def worker(started: asyncio.Event, cancelled: asyncio.Event, release: asyncio.Event):
    async def consume() -> None:
        started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            cancelled.set()
            await release.wait()
            raise

    return consume


def applied(journal: Journal, request: ControlRequest) -> bool:
    return any(event.body.get("kind") == "control_decision"
               and event.body.get("request") == request.model_dump(mode="json")
               and event.body.get("applied") is True for event in journal.read())


def owner_for(inbox, active: ActiveDriver, started, cancelled, release) -> DaemonTasks:
    owner: DaemonTasks

    async def control() -> None:
        await kill_worker_stop_consumer(inbox, active, owner)()

    owner = DaemonTasks(watcher=worker(started[0], cancelled[0], release),
                        merge=worker(started[1], cancelled[1], release),
                        box=worker(started[2], cancelled[2], release), control=control)
    return owner


@pytest.mark.asyncio
async def test_kill_waits_for_executor_and_worker_observation_before_journaling_applied(tmp_path):
    fs = LocalFilesystem()
    active = ActiveDriver()
    started = [asyncio.Event() for _ in range(3)]
    cancelled = [asyncio.Event() for _ in range(3)]
    release = asyncio.Event()
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        inbox = compose_daemon_control(state_dir=tmp_path, journal=journal, fs=fs)
        owner = owner_for(inbox, active, started, cancelled, release)
        owner.start()
        await asyncio.gather(*(event.wait() for event in started))
        request = ControlRequest(action="kill", lifecycle=inbox.lifecycle)
        publish_control(tmp_path, request, fs)

        await active.aborting.wait()
        assert not any(event.is_set() for event in cancelled)
        assert not applied(journal, request)

        active.unwind.set()
        await asyncio.gather(*(event.wait() for event in cancelled))
        assert not applied(journal, request)
        assert owner._control is not None and not owner._control.cancelled()

        release.set()
        while not applied(journal, request):
            await asyncio.sleep(0)
        assert all(task.done() for task in owner._workers)
        await owner.shutdown()


@pytest.mark.asyncio
async def test_stale_and_repeated_kills_do_not_restart_or_leave_workers_pending(tmp_path):
    fs = LocalFilesystem()
    active = ActiveDriver()
    active.unwind.set()
    started = [asyncio.Event() for _ in range(3)]
    cancelled = [asyncio.Event() for _ in range(3)]
    release = asyncio.Event()
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        inbox = compose_daemon_control(state_dir=tmp_path, journal=journal, fs=fs)
        owner = owner_for(inbox, active, started, cancelled, release)
        owner.start()
        await asyncio.gather(*(event.wait() for event in started))
        stale = ControlRequest(action="kill", lifecycle=uuid4())
        publish_control(tmp_path, stale, fs)
        while not any(event.body.get("request") == stale.model_dump(mode="json")
                          for event in journal.read()):
            await asyncio.sleep(0)
        assert active.aborts == 0
        assert all(not task.done() for task in owner._workers)

        request = ControlRequest(action="kill", lifecycle=inbox.lifecycle)
        publish_control(tmp_path, request, fs)
        await asyncio.gather(*(event.wait() for event in cancelled))
        release.set()
        while not applied(journal, request):
            await asyncio.sleep(0)
        again = ControlRequest(action="kill", lifecycle=inbox.lifecycle)
        publish_control(tmp_path, again, fs)
        while not applied(journal, again):
            await asyncio.sleep(0)
        assert active.aborts == 2
        assert all(task.done() for task in owner._workers)
        await owner.shutdown()


@pytest.mark.asyncio
async def test_run_keeps_control_task_alive_to_journal_the_kill(tmp_path):
    fs = LocalFilesystem()
    active = ActiveDriver()
    active.unwind.set()
    started = [asyncio.Event() for _ in range(3)]
    cancelled = [asyncio.Event() for _ in range(3)]
    release = asyncio.Event()
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        inbox = compose_daemon_control(state_dir=tmp_path, journal=journal, fs=fs)
        owner = owner_for(inbox, active, started, cancelled, release)
        run = asyncio.create_task(owner.run())
        await asyncio.gather(*(event.wait() for event in started))
        request = ControlRequest(action="kill", lifecycle=inbox.lifecycle)
        publish_control(tmp_path, request, fs)
        await asyncio.gather(*(event.wait() for event in cancelled))
        release.set()
        while not applied(journal, request):
            await asyncio.sleep(0)
        assert owner._control is not None and not owner._control.cancelled()
        assert not run.done()
        run.cancel()
        with pytest.raises(asyncio.CancelledError):
            await run
        assert all(task.done() for task in owner._workers)
