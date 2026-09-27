"""Task-lifetime contracts used by the production serve owner."""

import asyncio
from datetime import datetime, timezone

import pytest

from squatch.control import ControlRequest, publish_control
from squatch.daemon import (DaemonTasks, box_consumer, compose_daemon_control,
                            control_consumer, rework_consumer, watcher_consumer)
from squatch.journal import Journal
from squatch.seams import LocalFilesystem


def blocking(started: asyncio.Event):
    async def consume():
        started.set()
        await asyncio.Future()

    return consume


@pytest.mark.asyncio
async def test_watcher_consumer_lifetime_repeats_callback_snapshots():
    observed = []
    repeated = asyncio.Event()
    others = [asyncio.Event(), asyncio.Event()]

    class Watcher:
        def observed(self, priority_snapshot):
            observed.append(tuple(priority_snapshot))

    async def snapshot():
        if len(observed) == 1:
            repeated.set()
        return ("urgent", "later")

    owner = DaemonTasks(watcher=watcher_consumer(Watcher(), snapshot),
                        merge=blocking(others[0]), box=blocking(others[1]),
                        control=blocking(asyncio.Event()))
    owner.start()
    await repeated.wait()
    await asyncio.gather(*(event.wait() for event in others))
    await owner.shutdown()

    assert observed[:2] == [("urgent", "later"), ("urgent", "later")]


@pytest.mark.asyncio
async def test_merge_consumer_lifetime_repeats_callback_supplied_sha():
    shas = []
    repeated = asyncio.Event()
    others = [asyncio.Event(), asyncio.Event()]

    class Rework:
        async def run(self, *, sha):
            shas.append(sha)
            if len(shas) == 2:
                repeated.set()

    async def sha():
        return "post-admission"

    owner = DaemonTasks(watcher=blocking(others[0]), merge=rework_consumer(Rework(), sha),
                        box=blocking(others[1]), control=blocking(asyncio.Event()))
    owner.start()
    await repeated.wait()
    await asyncio.gather(*(event.wait() for event in others))
    await owner.shutdown()

    assert shas[:2] == ["post-admission", "post-admission"]


@pytest.mark.asyncio
async def test_box_consumer_lifetime_repeats_one_triage_pass():
    passes = []
    repeated = asyncio.Event()
    others = [asyncio.Event(), asyncio.Event()]
    spec = object()

    class Triage:
        async def run(self, received):
            passes.append(received)
            if len(passes) == 2:
                repeated.set()

    owner = DaemonTasks(watcher=blocking(others[0]), merge=blocking(others[1]),
                        box=box_consumer(Triage(), spec),
                        control=blocking(asyncio.Event()))
    owner.start()
    await repeated.wait()
    await asyncio.gather(*(event.wait() for event in others))
    await owner.shutdown()

    assert passes[:2] == [spec, spec]


@pytest.mark.asyncio
async def test_clean_shutdown_cancels_and_awaits_all_consumers():
    started = [asyncio.Event() for _ in range(4)]
    cancelled = []

    def callback(index):
        async def consume():
            started[index].set()
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                cancelled.append(index)
                raise

        return consume

    owner = DaemonTasks(watcher=callback(0), merge=callback(1), box=callback(2),
                        control=callback(3))
    owner.start()
    await asyncio.gather(*(event.wait() for event in started))
    await owner.shutdown()

    assert sorted(cancelled) == [0, 1, 2, 3]


@pytest.mark.asyncio
async def test_owner_cancellation_cancels_and_awaits_consumers():
    started = asyncio.Event()
    cancelled = []

    async def wait():
        started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    owner = DaemonTasks(watcher=wait, merge=wait, box=wait, control=wait)
    run = asyncio.create_task(owner.run())
    await started.wait()
    run.cancel()
    with pytest.raises(asyncio.CancelledError):
        await run

    assert len(cancelled) == 4


@pytest.mark.asyncio
async def test_shutdown_cancels_and_awaits_siblings_before_reraising_callback_exception():
    siblings_started = asyncio.Event()
    cancelled = []
    failure = RuntimeError("merge failed")

    async def watcher():
        siblings_started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            cancelled.append("watcher")
            raise

    async def merge():
        await siblings_started.wait()
        raise failure

    async def box():
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            cancelled.append("box")
            raise

    owner = DaemonTasks(watcher=watcher, merge=merge, box=box,
                        control=blocking(asyncio.Event()))
    owner.start()
    await siblings_started.wait()
    await asyncio.sleep(0)
    with pytest.raises(RuntimeError, match="merge failed"):
        await owner.shutdown()

    assert sorted(cancelled) == ["box", "watcher"]


@pytest.mark.asyncio
async def test_control_consumer_repeats_the_lock_holders_inbox_pass():
    requests = []
    repeated = asyncio.Event()
    others = [asyncio.Event(), asyncio.Event(), asyncio.Event()]

    class Inbox:
        async def consume(self, mutate):
            request = object()
            await mutate(request)
            if len(requests) == 2:
                repeated.set()

    async def mutate(request):
        requests.append(request)

    owner = DaemonTasks(
        watcher=blocking(others[0]), merge=blocking(others[1]),
        box=blocking(others[2]), control=control_consumer(Inbox(), mutate))
    owner.start()
    await repeated.wait()
    await asyncio.gather(*(event.wait() for event in others))
    await owner.shutdown()

    assert len(requests) >= 2


@pytest.mark.asyncio
async def test_control_composition_journals_through_the_lock_holders_handle(tmp_path):
    fs = LocalFilesystem()
    mutated = []
    with Journal(
            tmp_path, clock=lambda: datetime(2026, 9, 26, tzinfo=timezone.utc)) as journal:
        inbox = compose_daemon_control(state_dir=tmp_path, journal=journal, fs=fs)
        request = ControlRequest(action="pause", lifecycle=inbox.lifecycle)
        publish_control(tmp_path, request, fs)

        async def mutate(received):
            mutated.append(received.request_id)

        await control_consumer(inbox, mutate)()
        events = list(journal.read())

    assert mutated == [request.request_id]
    assert events[-1].key == f"control/{request.request_id}"
