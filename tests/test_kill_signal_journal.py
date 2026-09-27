"""The dormant kill request boundary owned by the journal lock holder."""

import argparse
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from squatch.__main__ import _parser
from squatch.control import ControlRequest, publish_control
from squatch.daemon import compose_daemon_control, control_consumer
from squatch.journal import Journal
from squatch.seams import LocalFilesystem


NOW = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)


def decisions(journal):
    return [event for event in journal.read()
            if event.type == "signal" and event.body.get("kind") == "control_decision"]


@pytest.mark.asyncio
async def test_lock_holder_journals_current_kill_before_its_governed_mutation(tmp_path):
    fs = LocalFilesystem()
    mutations = []
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        inbox = compose_daemon_control(state_dir=tmp_path, journal=journal, fs=fs)
        request = ControlRequest(action="kill", lifecycle=inbox.lifecycle)
        path = publish_control(tmp_path, request, fs)

        async def cancel(received):
            accepted, = decisions(journal)
            assert accepted.body["outcome"] == "accepted"
            assert accepted.body["request"] == received.model_dump(mode="json")
            assert not accepted.body["applied"]
            mutations.append(received.request_id)

        assert mutations == [] and path.exists()
        await control_consumer(inbox, cancel)()

        accepted, completed = decisions(journal)

    assert mutations == [request.request_id]
    assert (accepted.body["outcome"], accepted.body["applied"]) == ("accepted", False)
    assert (completed.body["outcome"], completed.body["applied"]) == ("accepted", True)
    assert not path.exists()


@pytest.mark.asyncio
async def test_stale_kill_identity_is_journaled_without_mutating(tmp_path):
    fs = LocalFilesystem()
    mutations = []
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        inbox = compose_daemon_control(state_dir=tmp_path, journal=journal, fs=fs)
        request = ControlRequest(action="kill", lifecycle=uuid4())
        publish_control(tmp_path, request, fs)

        async def cancel(received):
            mutations.append(received.request_id)

        await control_consumer(inbox, cancel)()
        stale, = decisions(journal)

    assert stale.body["outcome"] == "stale"
    assert stale.body["request"] == request.model_dump(mode="json")
    assert mutations == []


def test_kill_boundary_is_dormant_and_not_a_cli_verb():
    subparsers = next(action for action in _parser()._actions
                      if isinstance(action, argparse._SubParsersAction))

    assert "kill" not in subparsers.choices
