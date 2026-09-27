"""The real production serve graph and its lifetime contracts."""

import asyncio
import threading
import time
from contextlib import contextmanager
from io import StringIO
from pathlib import Path

import pytest

import squatch.__main__ as main_module
import squatch.daemon as daemon_module
import squatch.runner as runner_module
from squatch.artifacts import OUTCOMES, Cost
from squatch.checkpoint import Checkpoint
from squatch.control import ControlInbox
from squatch.daemon import DaemonTasks
from squatch.diagnose import DiagnosisRecord
from squatch.heartbeat import Heartbeat
from squatch.lockfile import LockHeld, Lockfile
from squatch.merge import Pipeline
from squatch.mergequeue import Admission, ConflictFacts, UnresolvedConflictHandoff
from squatch.rework import Rework
from squatch.serve import ServeGraph
from squatch.stages import Delivery, Stages
from squatch.triage import Triage
from test_cli import STATE, T0, author, checkout, git_env  # noqa: F401


def test_cli_constructs_every_boundary_after_reconcile_without_launching_host_work(
        checkout, monkeypatch):
    trace = []
    original_reconcile = runner_module.reconcile
    original_timers = daemon_module.compose_daemon_timers
    original_storm = main_module.compose_daemon_storm_producer

    async def reconcile(**kwargs):
        trace.append("reconcile")
        return await original_reconcile(**kwargs)

    def timers(**kwargs):
        trace.append("timers")
        composed = original_timers(**kwargs)
        shutdown = composed.shutdown

        async def stop():
            await shutdown()
            trace.append("timers stopped")

        composed.shutdown = stop
        return composed

    @contextmanager
    def storm(**kwargs):
        trace.append("storm")
        with original_storm(**kwargs):
            yield
        trace.append("storm stopped")

    async def inspect(self):
        assert trace == ["reconcile", "timers", "storm"]
        assert isinstance(self.pipeline, Pipeline)
        assert self.pipeline.admission_mode == "daemon"
        assert isinstance(self.rework, Rework)
        assert isinstance(self.triage, Triage)
        assert isinstance(self.control, ControlInbox)
        assert isinstance(self.checkpoint, Checkpoint)
        assert isinstance(self.heartbeat, Heartbeat)
        assert isinstance(self.tasks, DaemonTasks)
        assert not self.tasks._tasks
        assert not self.heartbeat.path.exists()
        with pytest.raises(LockHeld):
            Lockfile(checkout / STATE, instance_id="probe", clock=lambda: T0).acquire()
        trace.append("graph")
        return 0

    monkeypatch.setattr(runner_module, "reconcile", reconcile)
    monkeypatch.setattr(daemon_module, "compose_daemon_timers", timers)
    monkeypatch.setattr(main_module, "compose_daemon_storm_producer", storm)
    monkeypatch.setattr(ServeGraph, "run", inspect)
    out = StringIO()

    assert main_module.main(
        ["serve"], cwd=checkout, env=git_env(checkout.parent), out=out,
        clock=lambda: T0) == 0
    assert trace == [
        "reconcile", "timers", "storm", "graph", "storm stopped", "timers stopped"]
    assert not any(event.body.get("to") == "running"
                   for event in main_module.read_events(checkout / STATE))
    with Lockfile(checkout / STATE, instance_id="after", clock=lambda: T0):
        pass


def test_live_serve_holds_one_writer_beats_and_exits_after_applied_kill(checkout):
    result = []
    out = StringIO()
    env = git_env(checkout.parent)
    thread = threading.Thread(target=lambda: result.append(main_module.main(
        ["serve"], cwd=checkout, env=env, out=out, clock=lambda: T0)))
    thread.start()

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        events = tuple(main_module.read_events(checkout / STATE))
        if (checkout / STATE / "heartbeat").exists() and any(
                event.body.get("kind") == "control_lifecycle" for event in events):
            break
        time.sleep(.01)
    else:
        pytest.fail(f"serve did not become live: {out.getvalue()}")

    with pytest.raises(LockHeld):
        Lockfile(checkout / STATE, instance_id="second", clock=lambda: T0).acquire()
    control = StringIO()
    assert main_module.main(
        ["kill"], cwd=checkout, env=env, out=control, clock=lambda: T0) == 0
    thread.join(5)

    assert not thread.is_alive()
    assert result == [0]
    decisions = [event.body for event in main_module.read_events(checkout / STATE)
                 if event.body.get("kind") == "control_decision"
                 and event.body.get("request", {}).get("action") == "kill"]
    assert [decision["applied"] for decision in decisions] == [False, True]
    assert not any(event.body.get("to") == "running"
                   for event in main_module.read_events(checkout / STATE))
    with Lockfile(checkout / STATE, instance_id="after", clock=lambda: T0):
        pass


def test_serve_selected_pipeline_routes_a_settled_delivery_to_its_composed_queue(
        checkout, monkeypatch):
    offered = []
    observed = []
    author(checkout, "candidate")

    async def inspect(self):
        async def settled(ticket, *, run_seq):
            return Delivery(
                outcome="ok", findings=[], slip=None, invoice=None, review=None,
                worktree=Path("/synthetic-candidate"), base="base", stage="review",
                reason=None, cost=Cost(tokens=0, seconds=0, attempts=0))

        async def precheck(ticket, delivery, *, run_seq):
            return None, []

        async def restore(worktree):
            return None

        async def admit_delivery(candidate, **kwargs):
            offered.append(candidate)
            facts = ConflictFacts(
                stem=candidate.stem, paths=("squatch/widget.py",), rung="rework")
            handoff = UnresolvedConflictHandoff(
                stem=candidate.stem, branch=candidate.branch,
                run_seq=candidate.run_seq, facts=facts)
            return Admission(
                outcome="rework", conflict_facts=facts, rework=handoff), None, []

        async def diagnose(ticket, delivery, *, run_seq):
            observed.append(delivery)
            assert delivery.outcome in OUTCOMES
            return DiagnosisRecord(
                run_seq=run_seq, outcome=delivery.outcome, call="synthetic",
                verdict="abandon-human", lessons=("resolve the conflict",),
                reason="unresolved conflict", detail=None)

        self.pipeline.stages.run = settled
        self.pipeline.merge._precheck = precheck
        self.pipeline.merge._restore_ticket_plane = restore
        self.pipeline.merge_queue.admit_delivery = admit_delivery
        self.pipeline.diagnose = diagnose
        await self.tasks._callbacks[0]()
        await self.dispatch.scheduler.join()
        return 0

    monkeypatch.setattr(ServeGraph, "run", inspect)
    out = StringIO()

    assert main_module.main(
        ["serve"], cwd=checkout, env=git_env(checkout.parent), out=out,
        clock=lambda: T0) == 0
    assert [(candidate.stem, candidate.run_seq) for candidate in offered] == [
        ("candidate", 0)]
    assert len(observed) == 1
    assert observed[0].outcome == "gate_failed"
    [finding] = observed[0].findings
    assert (finding.code, finding.path) == ("post_rebase_regate", "squatch/widget.py")
    terminals = [event.body for event in main_module.read_events(checkout / STATE)
                 if event.type == "state_transition" and event.ticket == "candidate"
                 and event.body.get("to") != "running"]
    assert [terminal["to"] for terminal in terminals] == ["gate_failed"]


def test_live_kill_reaches_the_pipeline_executor_before_serve_releases_lock(
        checkout, monkeypatch):
    author(checkout, "candidate")
    started = threading.Event()
    unwound = threading.Event()
    active = {}

    async def run(self, ticket, *, run_seq):
        active["task"] = asyncio.current_task()
        started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            unwound.set()
            raise

    async def abort(self):
        task = active["task"]
        task.cancel()
        await asyncio.wait((task,))

    monkeypatch.setattr(Stages, "run", run)
    monkeypatch.setattr(Stages, "abort_active", abort)
    result = []
    out = StringIO()
    env = git_env(checkout.parent)
    thread = threading.Thread(target=lambda: result.append(main_module.main(
        ["serve"], cwd=checkout, env=env, out=out, clock=lambda: T0)))
    thread.start()
    assert started.wait(5)

    assert main_module.main(
        ["kill"], cwd=checkout, env=env, out=StringIO(), clock=lambda: T0) == 0
    thread.join(5)

    assert unwound.is_set()
    assert not thread.is_alive()
    assert result == [0]
    decisions = [event.body for event in main_module.read_events(checkout / STATE)
                 if event.body.get("kind") == "control_decision"
                 and event.body.get("request", {}).get("action") == "kill"]
    assert [decision["applied"] for decision in decisions] == [False, True]
    with Lockfile(checkout / STATE, instance_id="after", clock=lambda: T0):
        pass
