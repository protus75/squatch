"""The dormant kill-to-Driver cancellation boundary."""

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from squatch.artifacts import Artifact
from squatch.control import ControlRequest, publish_control
from squatch.daemon import compose_daemon_control, driver_abort_consumer
from squatch.driver import Driver, LLMStage, Spool
from squatch.enginelog import EngineLog
from squatch.journal import Journal
from squatch.redact import Redactor
from squatch.seams import LocalFilesystem


NOW = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)


class Echo(Artifact):
    text: str


class HangingEffect:
    stuck_seconds = 1

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()
        self.release = asyncio.Event()

    async def call(self, _request, **_call) -> object:
        self.started.set()
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            self.cancelled.set()
            await self.release.wait()
            raise
        raise AssertionError("test invocation was released before cancellation")


def driver(tmp_path: Path, effect: HangingEffect) -> Driver:
    fs = LocalFilesystem()
    return Driver(llm=effect, spool=Spool(tmp_path, fs=fs, redact=Redactor({})),
                  log=EngineLog(tmp_path, clock=lambda: NOW, redact=Redactor({})),
                  clock=lambda: NOW)


def stage() -> LLMStage:
    return LLMStage(name="review", surface="review", spec_version="test@1",
                    tier="medium", effort="medium", consumes=Echo, emits=Echo,
                    gates=(), render=lambda _inputs, _findings: "wait")


async def invoke(active: Driver) -> object:
    return await active.run(
        stage(), Echo(text="input", produced_by_spec_version="test@1", produced_at_sha="abc"),
        ticket="ticket", run_seq=1, attempt=1, workspace=Path("/workspace"), sha="abc")


@pytest.mark.asyncio
async def test_journaled_kill_cancels_and_unwinds_the_active_driver_invocation(tmp_path):
    fs = LocalFilesystem()
    effect = HangingEffect()
    active = driver(tmp_path, effect)
    invocation = asyncio.create_task(invoke(active))
    await effect.started.wait()

    with Journal(tmp_path, clock=lambda: NOW) as journal:
        inbox = compose_daemon_control(state_dir=tmp_path, journal=journal, fs=fs)
        request = ControlRequest(action="kill", lifecycle=inbox.lifecycle)
        publish_control(tmp_path, request, fs)
        consumer = asyncio.create_task(driver_abort_consumer(inbox, active)())
        await effect.cancelled.wait()
        assert not consumer.done()
        effect.release.set()
        await consumer
        decisions = [event for event in journal.read()
                     if event.body.get("kind") == "control_decision"]

    with pytest.raises(asyncio.CancelledError):
        await invocation
    assert decisions[-1].body["outcome"] == "accepted"
    assert decisions[-1].body["applied"] is True


@pytest.mark.asyncio
async def test_cancelling_the_control_consumer_is_not_swallowed_during_unwind(tmp_path):
    fs = LocalFilesystem()
    effect = HangingEffect()
    active = driver(tmp_path, effect)
    invocation = asyncio.create_task(invoke(active))
    await effect.started.wait()

    with Journal(tmp_path, clock=lambda: NOW) as journal:
        inbox = compose_daemon_control(state_dir=tmp_path, journal=journal, fs=fs)
        publish_control(tmp_path, ControlRequest(action="kill", lifecycle=inbox.lifecycle), fs)
        consumer = asyncio.create_task(driver_abort_consumer(inbox, active)())
        await effect.cancelled.wait()
        consumer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await consumer

    effect.release.set()
    with pytest.raises(asyncio.CancelledError):
        await invocation
