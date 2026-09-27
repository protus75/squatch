"""The kill CLI activated through the production bootstrap-drain composition."""

import argparse
import asyncio
import threading
import time
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from uuid import uuid4

import pytest

import squatch.__main__ as main_module
from squatch.artifacts import Artifact
from squatch.control import ControlRequest, publish_control
from squatch.drain import Drain
from squatch.driver import LLMStage
from squatch.journal import Journal, read_events
from squatch.lockfile import Lockfile
from squatch.seams import LocalFilesystem
from squatch.stages import Stages
from test_cli import STATE, author, checkout, git_env  # noqa: F401


NOW = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)


class Echo(Artifact):
    text: str


class HangingEffect:
    stuck_seconds = 1

    def __init__(self) -> None:
        self.started = threading.Event()
        self.cancelled = threading.Event()
        self.release = threading.Event()
        self.unwound = threading.Event()

    async def call(self, _request, **_call):
        self.started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            self.cancelled.set()
            while not self.release.is_set():
                await asyncio.sleep(0)
            self.unwound.set()
            raise


def decisions(state: Path, action: str = "kill") -> list[dict]:
    return [event.body for event in read_events(state)
            if event.body.get("kind") == "control_decision"
            and event.body.get("request", {}).get("action") == action]


def run_owned_driver(effect: HangingEffect):
    async def run(self, ticket, *, run_seq):
        self._driver._llm = effect
        stage = LLMStage(
            name="implement", surface="implement", spec_version="test@1",
            tier="medium", effort="medium", consumes=Echo, emits=Echo,
            gates=(), render=lambda _inputs, _findings: "wait")
        await self._driver.run(
            stage,
            Echo(text="input", produced_by_spec_version="test@1", produced_at_sha="abc"),
            ticket=ticket.stem, run_seq=run_seq, attempt=1,
            workspace=Path("/workspace"), sha="abc")
        raise AssertionError("the cancelled Driver invocation returned")

    return run


def test_no_engine_kill_refuses_without_creating_control_state(checkout):
    state = checkout / STATE
    out = StringIO()

    result = main_module.main(
        ["kill"], cwd=checkout, env=git_env(checkout.parent), out=out, clock=lambda: NOW)

    assert result == 2
    assert out.getvalue().startswith("refused: nothing running to kill\n")
    assert "paved road:" in out.getvalue()
    assert not [event for event in read_events(state)
                if event.body.get("kind") in {
                    "control_lifecycle", "control_decision", "control_hold"}]
    assert not (state / "control").exists()


@pytest.mark.asyncio
async def test_stale_kill_does_not_latch_or_reach_the_bound_stage_abort(tmp_path):
    state = tmp_path / "state"
    fs = LocalFilesystem()
    aborts = 0

    async def abort() -> None:
        nonlocal aborts
        aborts += 1

    with (Lockfile(state, instance_id="drain", clock=lambda: NOW),
          Journal(state, clock=lambda: NOW) as journal):
        control, _wait = main_module._control_factory(state, lambda: None)(journal)
        control.bind_abort(abort)
        request = ControlRequest(action="kill", lifecycle=uuid4())
        publish_control(state, request, fs)

        assert await control.allow_offer()
        stale, = decisions(state)
        assert stale["outcome"] == "stale"
        assert not stale["applied"]
        assert not control.stopping
        assert aborts == 0


def test_live_kill_unwinds_the_stages_driver_and_stops_later_admission_or_retry(
        checkout, monkeypatch):
    state = checkout / STATE
    author(checkout, "first")
    author(checkout, "second")
    with Journal(state, clock=lambda: NOW) as journal:
        for stem in ("first", "second"):
            journal.append("state_transition", {"to": "gate_failed", "run_seq": 0},
                           ticket=stem)

    effect = HangingEffect()
    monkeypatch.setattr(Stages, "run", run_owned_driver(effect))
    result: list[int] = []
    out = StringIO()
    thread = threading.Thread(
        target=lambda: result.append(main_module.main(
            ["drain"], cwd=checkout, env=git_env(checkout.parent), out=out,
            clock=lambda: NOW)))
    thread.start()
    assert effect.started.wait(5)

    control_out = StringIO()
    assert main_module.main(
        ["kill"], cwd=checkout, env=git_env(checkout.parent), out=control_out,
        clock=lambda: NOW) == 0
    assert control_out.getvalue() == "published kill\n"
    assert effect.cancelled.wait(5)

    pending = decisions(state)
    assert [decision["applied"] for decision in pending] == [False]
    assert pending[0]["outcome"] == "accepted"
    effect.release.set()
    thread.join(5)

    assert not thread.is_alive()
    assert effect.unwound.is_set()
    assert result == [0]
    assert [decision["applied"] for decision in decisions(state)] == [False, True]
    events = tuple(read_events(state))
    assert [event.body["to"] for event in events
            if event.type == "state_transition" and event.ticket == "first"] == [
                "gate_failed", "running"]
    assert [event.body["to"] for event in events
            if event.type == "state_transition" and event.ticket == "second"] == [
                "gate_failed"]
    assert [event.ticket for event in events if event.type == "cap_consumed"] == ["first"]
    assert "stopped: kill accepted" in out.getvalue()


def test_kill_while_paused_stops_without_admission_or_retry_draw(checkout, monkeypatch):
    state = checkout / STATE
    author(checkout, "first")
    with Journal(state, clock=lambda: NOW) as journal:
        journal.append("state_transition", {"to": "gate_failed", "run_seq": 0},
                       ticket="first")

    reached_scan = threading.Event()
    release_scan = threading.Event()
    original_scan = Drain._scan

    async def wait_at_scan(self, facts):
        reached_scan.set()
        while not release_scan.is_set():
            await asyncio.sleep(0)
        return await original_scan(self, facts)

    monkeypatch.setattr(Drain, "_scan", wait_at_scan)
    result: list[int] = []
    out = StringIO()
    thread = threading.Thread(
        target=lambda: result.append(main_module.main(
            ["drain"], cwd=checkout, env=git_env(checkout.parent), out=out,
            clock=lambda: NOW)))
    thread.start()
    assert reached_scan.wait(5)

    pause_out = StringIO()
    assert main_module.main(
        ["pause"], cwd=checkout, env=git_env(checkout.parent), out=pause_out,
        clock=lambda: NOW) == 0
    release_scan.set()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if any(decision["applied"] for decision in decisions(state, "pause")):
            break
        time.sleep(.01)
    else:
        pytest.fail("the live drain did not apply pause")

    kill_out = StringIO()
    assert main_module.main(
        ["kill"], cwd=checkout, env=git_env(checkout.parent), out=kill_out,
        clock=lambda: NOW) == 0
    thread.join(5)

    assert not thread.is_alive()
    assert result == [0]
    assert kill_out.getvalue() == "published kill\n"
    assert "stopped: kill accepted" in out.getvalue()
    assert [decision["applied"] for decision in decisions(state)] == [False, True]
    with Lockfile(state, instance_id="probe", clock=lambda: NOW):
        pass
    events = tuple(read_events(state))
    assert not [event for event in events if event.type == "cap_consumed"]
    assert [event.body["to"] for event in events
            if event.type == "state_transition" and event.ticket == "first"] == ["gate_failed"]


def test_dispatch_control_failure_unwinds_the_driver_before_main_exits(checkout, monkeypatch):
    state = checkout / STATE
    author(checkout, "first")
    effect = HangingEffect()
    effect.release.set()
    monkeypatch.setattr(Stages, "run", run_owned_driver(effect))
    original_factory = main_module._control_factory

    async def fail_after_dispatch_starts(_seconds):
        while not effect.started.is_set():
            await asyncio.sleep(0)
        raise RuntimeError("control consumer failed")

    monkeypatch.setattr(
        main_module, "_control_factory",
        lambda state_dir, supplier: original_factory(
            state_dir, supplier, poll_sleep=fail_after_dispatch_starts))

    with pytest.raises(RuntimeError, match="control consumer failed"):
        main_module.main(
            ["drain"], cwd=checkout, env=git_env(checkout.parent), out=StringIO(),
            clock=lambda: NOW)

    assert effect.cancelled.is_set()
    assert effect.unwound.is_set()
    with Lockfile(state, instance_id="probe", clock=lambda: NOW):
        pass
    assert [event.body["to"] for event in read_events(state)
            if event.type == "state_transition" and event.ticket == "first"] == ["running"]


def test_cli_composition_binds_only_the_production_stages_abort(checkout, monkeypatch):
    bound = []
    original = main_module.compose_pipeline

    def compose(**kwargs):
        pipeline = original(**kwargs)
        bound.append(pipeline.stages)
        return pipeline

    monkeypatch.setattr(main_module, "compose_pipeline", compose)
    args = argparse.Namespace(config=None, verb="drain")

    async def inspect(runner, _config, _git, control):
        async with runner.session() as session:
            pause, _wait = control(session.journal)
            pipeline = runner._pipeline(session.journal)
            assert pipeline.stages is bound[0]
            assert pause._abort == pipeline.stages.abort_active
        return 0

    assert main_module._locked(
        args, checkout, git_env(checkout.parent), StringIO(), None, lambda: NOW,
        main_module.SubprocessExec(), inspect) == 0
    assert len(bound) == 1
