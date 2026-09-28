"""Production restart delegation and session-owned journaled deadlines."""

import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
from io import StringIO

import pytest

import squatch.__main__ as main_module
import squatch.daemon as daemon_module
import squatch.runner as runner_module
from squatch.daemon import compose_daemon_restart, compose_daemon_timers
from squatch.journal import Journal, JournalCorruption, read_events
from squatch.lockfile import LockHeld, Lockfile
from squatch.reconcile import reconcile
from squatch.config import parse
from squatch.providers import Registry
from squatch.runner import RecoveredSession
from squatch.timers import fold_deadlines
from test_cli import FakePipeline, STATE, T0, author, checkout, git_env  # noqa: F401
from test_drain import retro_stages


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now


class Sleep:
    def __init__(self):
        self.calls = []
        self.waiting = asyncio.Queue()

    async def __call__(self, seconds):
        self.calls.append(seconds)
        wake = asyncio.get_running_loop().create_future()
        self.waiting.put_nowait(wake)
        await wake

    async def next(self):
        return await asyncio.wait_for(self.waiting.get(), 1)


def timer_events(journal):
    return [(event.type, event.key) for event in journal.read()
            if event.body.get("kind") == "deadline"]


@pytest.mark.parametrize("verb", ["run", "drain"])
def test_main_restart_delegates_real_reconcile_once_before_first_offer(
        checkout, monkeypatch, verb):
    author(checkout, "candidate")
    state = checkout / STATE
    clock = Clock()
    with Journal(state, clock=clock) as journal:
        journal.append("state_transition", {"to": "running", "run_seq": 0},
                       ticket="interrupted")

        async def seed():
            timers = compose_daemon_timers(journal=journal, clock=clock)
            timers.arm("expired", T0 + timedelta(seconds=1))
            timers.arm("pending", T0 + timedelta(days=1))
            await timers.shutdown()

        asyncio.run(seed())
    clock.now += timedelta(seconds=2)
    trace, owned = [], []
    original_restart = main_module.compose_daemon_restart
    original_timers = daemon_module.compose_daemon_timers
    original_dispatch = runner_module.Runner.dispatch
    assert runner_module.reconcile is reconcile

    def composed_restart(**kwargs):
        trace.append("restart")
        return original_restart(**kwargs)

    async def observed_reconcile(**kwargs):
        assert not kwargs["journal"].closed
        with pytest.raises(LockHeld):
            Lockfile(state, instance_id="probe", clock=clock).acquire()
        trace.append("reconcile")
        found = await reconcile(**kwargs)
        assert [orphan.stem for orphan in found] == ["interrupted"]
        trace.append("reaped")
        return found

    def composed_timers(**kwargs):
        assert trace == ["restart", "reconcile", "reaped"]
        assert kwargs["clock"] is clock
        journal = kwargs["journal"]
        started = asyncio.Event()

        async def sleep(_seconds):
            started.set()
            try:
                await asyncio.Future()
            finally:
                assert not journal.closed
                trace.append("timers stopped")

        timers = original_timers(**kwargs, sleep=sleep)
        owned.append((timers, journal, started))
        trace.append("timers")
        return timers

    async def dispatch(self, ticket, journal):
        assert trace == ["restart", "reconcile", "reaped", "timers"]
        assert any(event.ticket == "interrupted" and event.body.get("to") == "abandoned"
                   for event in journal.read())
        assert timer_events(journal).count(("timer_fired", "expired")) == 1
        await asyncio.wait_for(owned[0][2].wait(), 1)
        trace.append("offer")
        return await original_dispatch(self, ticket, journal)

    monkeypatch.setattr(main_module, "compose_daemon_restart", composed_restart)
    monkeypatch.setattr(runner_module, "reconcile", observed_reconcile)
    monkeypatch.setattr(daemon_module, "compose_daemon_timers", composed_timers)
    monkeypatch.setattr(runner_module.Runner, "dispatch", dispatch)
    pipeline = FakePipeline("premise_failed")
    out = StringIO()
    args = ["run", "candidate"] if verb == "run" else ["drain"]

    def pipeline_factory(journal):
        if verb == "drain":
            pipeline.stages, _llm = retro_stages(journal)
        return pipeline

    result = main_module.main(args, cwd=checkout, env=git_env(checkout.parent), out=out,
                              pipeline=pipeline_factory, clock=clock)

    assert result == (1 if verb == "run" else 0), out.getvalue()
    assert trace == ["restart", "reconcile", "reaped", "timers", "offer", "timers stopped"]
    assert pipeline.calls == [("candidate", 0)]
    assert len(owned) == 1 and owned[0][1].closed
    assert not (state / "heartbeat").exists()


async def test_restart_delegates_entry_and_unwinds_timers_before_session_exit(tmp_path, monkeypatch):
    trace = []
    clock = Clock()
    original = daemon_module.compose_daemon_timers

    @asynccontextmanager
    async def session():
        with Journal(tmp_path, clock=clock) as journal:
            trace.append("reconcile")
            try:
                yield RecoveredSession(journal, None)
            finally:
                trace.append("session exit")

    def timers(**kwargs):
        result = original(**kwargs)
        shutdown = result.shutdown

        async def stop():
            assert not kwargs["journal"].closed
            await shutdown()
            trace.append("shutdown")

        result.shutdown = stop
        return result

    monkeypatch.setattr(daemon_module, "compose_daemon_timers", timers)
    with pytest.raises(RuntimeError, match="dispatch failed"):
        async with compose_daemon_restart(
                session=session(),
                registry=Registry(parse({"schema_version": 1, "state_dir": ".state",
                                         "providers": [], "routing": []}, source="test")),
                clock=clock):
            trace.append("dispatch")
            raise RuntimeError("dispatch failed")
    assert trace == ["reconcile", "dispatch", "shutdown", "session exit"]


async def test_deadline_persists_rearms_once_and_uses_clock_after_early_wake(tmp_path):
    clock, first_sleep = Clock(), Sleep()
    due = T0 + timedelta(seconds=20)
    with Journal(tmp_path, clock=clock) as journal:
        timers = compose_daemon_timers(journal=journal, clock=clock, sleep=first_sleep)
        timers.arm("cooldown", due)
        timers.arm("cooldown", due)
        await first_sleep.next()
        assert first_sleep.calls == [20]
        assert timer_events(journal) == [("timer_armed", "cooldown")]
        await timers.shutdown()

    clock.now += timedelta(seconds=5)
    sleep = Sleep()
    with Journal(tmp_path, clock=clock) as journal:
        timers = compose_daemon_timers(journal=journal, clock=clock, sleep=sleep)
        timers.rearm()
        wake = await sleep.next()
        assert sleep.calls == [15]
        clock.now += timedelta(seconds=4)
        wake.set_result(None)
        wake = await sleep.next()
        assert sleep.calls == [15, 11]
        assert timer_events(journal) == [("timer_armed", "cooldown")]
        clock.now = due
        wake.set_result(None)
        await asyncio.sleep(0)
        timers.rearm()
        timers.arm("cooldown", due)
        await timers.shutdown()
        assert timer_events(journal) == [("timer_armed", "cooldown"),
                                         ("timer_fired", "cooldown")]
        assert tuple(journal.read())[-1].ts == due.isoformat()

    with Journal(tmp_path, clock=clock) as journal:
        timers = compose_daemon_timers(journal=journal, clock=clock, sleep=sleep)
        timers.rearm()
        timers.arm("cooldown", due)
        await asyncio.sleep(0)
        await timers.shutdown()
        assert sleep.calls == [15, 11]
        assert timer_events(journal).count(("timer_fired", "cooldown")) == 1
    assert {path.name for path in tmp_path.iterdir()} == {"journal"}


async def test_expired_deadline_fires_during_composition_once_across_restarts(tmp_path):
    clock, sleep = Clock(), Sleep()
    with Journal(tmp_path, clock=clock) as journal:
        timers = compose_daemon_timers(journal=journal, clock=clock, sleep=sleep)
        timers.arm("expired", T0 + timedelta(seconds=1))
        await timers.shutdown()
    clock.now += timedelta(seconds=2)
    for _ in range(2):
        with Journal(tmp_path, clock=clock) as journal:
            timers = compose_daemon_timers(journal=journal, clock=clock, sleep=sleep)
            timers.rearm()
            assert timer_events(journal) == [("timer_armed", "expired"),
                                             ("timer_fired", "expired")]
            await timers.shutdown()
    assert sleep.calls == []


async def test_shutdown_observes_pending_tasks_before_journal_closes(tmp_path):
    clock = Clock()
    started, stopped = asyncio.Event(), []
    with Journal(tmp_path, clock=clock) as journal:
        async def sleep(_seconds):
            started.set()
            try:
                await asyncio.Future()
            finally:
                stopped.append(not journal.closed)

        timers = compose_daemon_timers(journal=journal, clock=clock, sleep=sleep)
        timers.arm("pending", T0 + timedelta(seconds=1))
        await asyncio.wait_for(started.wait(), 1)
        await timers.shutdown()
        assert stopped == [True]
    with pytest.raises(ValueError, match="closed file"):
        journal.append("signal", {})
    clock.now += timedelta(seconds=2)
    await asyncio.sleep(0)
    assert [(event.type, event.key) for event in read_events(tmp_path)] == [
        ("timer_armed", "pending")]
    with pytest.raises(RuntimeError, match="shut down"):
        timers.rearm()


async def test_failed_timer_write_is_observed_at_shutdown(tmp_path, monkeypatch):
    clock, sleep = Clock(), Sleep()
    with Journal(tmp_path, clock=clock) as journal:
        timers = compose_daemon_timers(journal=journal, clock=clock, sleep=sleep)
        timers.arm("pending", T0 + timedelta(seconds=1))
        wake = await sleep.next()
        append = journal.append

        def fail(type, body, **kwargs):
            if type == "timer_fired":
                raise OSError("journal unavailable")
            return append(type, body, **kwargs)

        monkeypatch.setattr(journal, "append", fail)
        clock.now += timedelta(seconds=2)
        wake.set_result(None)
        await asyncio.sleep(0)
        with pytest.raises(OSError, match="journal unavailable"):
            await timers.shutdown()
        assert timer_events(journal) == [("timer_armed", "pending")]


async def test_deadline_identity_validation_and_other_timer_ownership(tmp_path):
    clock = Clock()
    with Journal(tmp_path, clock=clock) as journal:
        journal.append("timer_armed", {"kind": "drain_max_runtime"})
        timers = compose_daemon_timers(journal=journal, clock=clock)
        with pytest.raises(ValueError, match="aware"):
            timers.arm("naive", T0.replace(tzinfo=None))
        with pytest.raises(ValueError, match="nonempty"):
            timers.arm("", T0)
        timers.arm("now", T0)
        with pytest.raises(ValueError, match="different time"):
            timers.arm("now", T0 + timedelta(seconds=1))
        # Even a repeated arm record cannot resurrect a fired identity.
        journal.append("timer_armed", {"kind": "deadline", "deadline": T0.isoformat()},
                       key="now")
        assert fold_deadlines(journal.read())["now"].fired
        await timers.shutdown()
        journal.append("timer_fired", {"kind": "deadline", "deadline": T0.isoformat()},
                       key="unknown")
        with pytest.raises(JournalCorruption, match="without an arm"):
            compose_daemon_timers(journal=journal, clock=clock)
