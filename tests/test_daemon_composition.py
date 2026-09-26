"""In-process harness for the production daemon composition."""

import argparse
import asyncio
from datetime import datetime, timezone
from io import StringIO

import pytest

from squatch.__main__ import _parser
import squatch.__main__ as main_module
from squatch.artifacts import Cost
from squatch.config import Config, parse
from squatch.daemon import (DaemonDispatch, DispatchAdmission,
                            compose_daemon_dispatch)
from squatch.scheduler import Scheduler
from squatch.merge import Pipeline
from squatch.mergequeue import MergeQueue
from squatch.stages import Delivery
from squatch.watcher import Watcher
from test_mergequeue import fixture_repo
from test_stages import PLAN, TICKET


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


def test_main_factory_and_runner_dispatch_receive_production_queue(tmp_path, monkeypatch):
    async def setup():
        repo, env, git = await fixture_repo(tmp_path, path="squatch/existing.py")
        (repo / "SQUATCH_PLAN.md").write_text(PLAN)
        (repo / "config.yaml").write_text(
            "schema_version: 1\nstate_dir: .state\nproviders: []\nrouting: []\n")
        path = repo / "tickets/candidate/ticket.md"
        path.parent.mkdir(parents=True)
        path.write_text(TICKET.format(verify="python -V", frontmatter="state: confirmed"))
        await git.add(repo, ["SQUATCH_PLAN.md", "config.yaml"])
        await git.commit(repo, "host configuration")
        return repo, env

    repo, env = asyncio.run(setup())
    constructed, dispatched = [], []
    original = main_module.compose_pipeline

    def compose(**kwargs):
        pipeline = original(**kwargs)
        constructed.append(pipeline)
        assert any(e.ticket == "candidate" and e.body.get("to") == "running"
                   for e in kwargs["journal"].read())
        return pipeline

    async def run(self, ticket, *, run_seq):
        dispatched.append(self)
        assert ticket.stem == "candidate" and isinstance(self.merge_queue, MergeQueue)
        return Delivery(outcome="already_satisfied", findings=[], slip=None, invoice=None,
                        review=None, worktree=repo, base="", stage="check", reason=None,
                        cost=Cost(tokens=0, seconds=0, attempts=0))

    monkeypatch.setattr(main_module, "compose_pipeline", compose)
    monkeypatch.setattr(Pipeline, "run", run)
    out = StringIO()
    result = main_module.main(["run", "candidate"], cwd=repo, env=env, out=out,
                              clock=lambda: datetime.now(timezone.utc))
    assert result == 0, out.getvalue()
    assert len(constructed) == 1 and dispatched == constructed
    assert isinstance(constructed[0].merge_queue, MergeQueue)
