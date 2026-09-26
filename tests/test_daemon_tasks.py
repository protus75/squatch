"""Task-lifetime contracts for the dormant daemon background consumers."""

import asyncio

import pytest

from squatch.daemon import DaemonTasks, box_consumer, rework_consumer, watcher_consumer


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
                        merge=blocking(others[0]), box=blocking(others[1]))
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
                        box=blocking(others[1]))
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
                        box=box_consumer(Triage(), spec))
    owner.start()
    await repeated.wait()
    await asyncio.gather(*(event.wait() for event in others))
    await owner.shutdown()

    assert passes[:2] == [spec, spec]


@pytest.mark.asyncio
async def test_clean_shutdown_cancels_and_awaits_all_consumers():
    started = [asyncio.Event() for _ in range(3)]
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

    owner = DaemonTasks(watcher=callback(0), merge=callback(1), box=callback(2))
    owner.start()
    await asyncio.gather(*(event.wait() for event in started))
    await owner.shutdown()

    assert sorted(cancelled) == [0, 1, 2]


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

    owner = DaemonTasks(watcher=wait, merge=wait, box=wait)
    run = asyncio.create_task(owner.run())
    await started.wait()
    run.cancel()
    with pytest.raises(asyncio.CancelledError):
        await run

    assert len(cancelled) == 3


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

    owner = DaemonTasks(watcher=watcher, merge=merge, box=box)
    owner.start()
    await siblings_started.wait()
    await asyncio.sleep(0)
    with pytest.raises(RuntimeError, match="merge failed"):
        await owner.shutdown()

    assert sorted(cancelled) == ["box", "watcher"]
