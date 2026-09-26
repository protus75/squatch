"""In-process harness for the production daemon composition."""

import argparse
import asyncio

import pytest

from squatch.__main__ import _parser
from squatch.config import Config, parse
from squatch.daemon import (DaemonDispatch, DispatchAdmission,
                            compose_daemon_dispatch)
from squatch.scheduler import Scheduler
from squatch.watcher import Watcher


def config(*, max_unmerged: int = 2) -> Config:
    return parse({
        "schema_version": 1,
        "state_dir": "state",
        "providers": [],
        "routing": [],
        "scheduler": {"max_unmerged": max_unmerged},
    }, source="test")


def test_composition_constructs_in_process_without_starting_work_or_adding_a_verb():
    calls: list[str] = []

    async def work(stem: str, captured: Config) -> None:
        calls.append(stem)

    composed = compose_daemon_dispatch(config, work)

    assert isinstance(composed, DaemonDispatch)
    assert isinstance(composed.admission, DispatchAdmission)
    assert isinstance(composed.scheduler, Scheduler)
    assert isinstance(composed.watcher, Watcher)
    assert calls == []
    subparsers = next(action for action in _parser()._actions
                      if isinstance(action, argparse._SubParsersAction))
    assert "serve" not in subparsers.choices


@pytest.mark.asyncio
async def test_composition_dispatches_through_admission_with_latest_priority_and_config():
    current = config()
    supplier_calls = 0
    started = asyncio.Event()
    release = asyncio.Event()
    calls: list[tuple[str, int]] = []
    active = 0
    maximum_active = 0

    def supplier() -> Config:
        nonlocal supplier_calls
        supplier_calls += 1
        return current

    async def work(stem: str, captured: Config) -> None:
        nonlocal active, maximum_active
        active += 1
        maximum_active = max(maximum_active, active)
        try:
            if stem == "running":
                started.set()
                await release.wait()
            calls.append((stem, captured.scheduler.max_unmerged))
        finally:
            active -= 1

    composed = compose_daemon_dispatch(supplier, work)
    composed.watcher.observed(("running", "stale"))
    await started.wait()

    assert composed.admission.admit("busy", work) is None
    current.scheduler.max_unmerged = 99
    composed.watcher.observed(("running", "middle"))
    composed.watcher.observed(("running", "priority", "next"))
    current = config(max_unmerged=7)
    release.set()
    await composed.scheduler.join()

    assert calls == [("running", 2), ("priority", 7), ("next", 7)]
    assert supplier_calls == 3
    assert maximum_active == 1
