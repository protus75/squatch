"""The daemon heartbeat is a seam-driven boundary activated by serve."""

import argparse
import asyncio
from datetime import datetime, timezone

import pytest

from squatch.__main__ import _parser
from squatch.daemon import DaemonTasks, compose_daemon_heartbeat


NOW = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)


class Filesystem:
    def __init__(self) -> None:
        self.writes = []

    def write(self, path, data) -> None:
        self.writes.append((path, data))


def blocking(started: asyncio.Event):
    async def consume():
        started.set()
        await asyncio.Future()

    return consume


@pytest.mark.asyncio
async def test_heartbeat_path_and_live_pass_use_only_injected_seams(tmp_path):
    fs = Filesystem()
    calls = []

    def clock():
        calls.append(True)
        return NOW

    tasks = DaemonTasks(watcher=lambda: _never(), merge=lambda: _never(),
                        box=lambda: _never(), control=lambda: _never())
    heartbeat = compose_daemon_heartbeat(state_dir=tmp_path, tasks=tasks, clock=clock, fs=fs)

    assert heartbeat.path == tmp_path / "heartbeat"
    assert not heartbeat.beat() and calls == [] and fs.writes == []

    tasks.start()
    try:
        assert heartbeat.beat()
    finally:
        await tasks.shutdown()

    assert calls == [True]
    assert fs.writes == [(tmp_path / "heartbeat", NOW.isoformat().encode())]


@pytest.mark.asyncio
async def test_heartbeat_skips_stopped_cancelled_and_terminal_workers(tmp_path):
    fs = Filesystem()
    tasks = DaemonTasks(watcher=blocking(asyncio.Event()), merge=blocking(asyncio.Event()),
                        box=blocking(asyncio.Event()), control=blocking(asyncio.Event()))
    heartbeat = compose_daemon_heartbeat(state_dir=tmp_path, tasks=tasks,
                                         clock=lambda: NOW, fs=fs)

    assert not heartbeat.beat()
    tasks.start()
    await asyncio.sleep(0)
    tasks._workers[0].cancel()
    assert not heartbeat.beat()
    await tasks.stop_workers()
    assert not heartbeat.beat()
    await tasks.shutdown()

    for terminal in ("watcher", "merge", "box"):
        fs.writes.clear()
        started = [asyncio.Event() for _ in range(3)]

        def callback(name, event):
            async def consume():
                event.set()
                if name == terminal:
                    raise RuntimeError(f"{name} failed")
                await asyncio.Future()

            return consume

        tasks = DaemonTasks(watcher=callback("watcher", started[0]),
                            merge=callback("merge", started[1]),
                            box=callback("box", started[2]),
                            control=blocking(asyncio.Event()))
        heartbeat = compose_daemon_heartbeat(state_dir=tmp_path, tasks=tasks,
                                             clock=lambda: NOW, fs=fs)
        tasks.start()
        await asyncio.gather(*(event.wait() for event in started))
        await asyncio.sleep(0)
        assert not heartbeat.beat()
        with pytest.raises(RuntimeError, match=f"{terminal} failed"):
            await tasks.shutdown()
        assert fs.writes == []


def test_heartbeat_construction_is_dormant_and_serve_is_registered(tmp_path):
    fs = Filesystem()
    tasks = DaemonTasks(watcher=lambda: _never(), merge=lambda: _never(),
                        box=lambda: _never(), control=lambda: _never())

    heartbeat = compose_daemon_heartbeat(state_dir=tmp_path, tasks=tasks,
                                         clock=lambda: NOW, fs=fs)

    assert heartbeat.path == tmp_path / "heartbeat"
    assert not tasks.workers_live and fs.writes == []
    subparsers = next(action for action in _parser()._actions
                      if isinstance(action, argparse._SubParsersAction))
    assert "serve" in subparsers.choices


async def _never():
    await asyncio.Future()
