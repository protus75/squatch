"""Pause at the production admission boundary, dormant until activation."""

import asyncio
from io import StringIO
from uuid import UUID, uuid4

import pytest

from test_cli import T0, checkout, git_env  # noqa: F401
from test_daemon_admission import config
from squatch.__main__ import main
from squatch.control import ControlInbox, ControlRequest, publish_control
from squatch.daemon import DispatchPause, compose_daemon_control, compose_daemon_dispatch
from squatch.journal import Journal
from squatch.seams import LocalFilesystem


@pytest.fixture
def boundary(tmp_path):
    fs = LocalFilesystem()
    with Journal(tmp_path, clock=lambda: T0) as journal:
        inbox = ControlInbox(tmp_path, journal=journal, fs=fs)
        pause = DispatchPause(inbox)

        def send(action, **kwargs):
            request = ControlRequest(action=action, lifecycle=kwargs.pop('lifecycle', inbox.lifecycle),
                                     **kwargs)
            publish_control(tmp_path, request, fs)
            return request

        yield pause, journal, send


async def test_real_dispatch_waits_before_snapshot_and_preserves_admitted_work(boundary, monkeypatch):
    pause, journal, send = boundary
    started, finish, waiting, resume = (asyncio.Event() for _ in range(4))
    calls, snapshots = [], []
    from squatch.daemon import snapshot

    def capture(value):
        snapshots.append(value)
        return snapshot(value)

    monkeypatch.setattr('squatch.daemon.snapshot', capture)

    async def work(stem, captured):
        calls.append(stem)
        if stem == 'first':
            started.set()
            await finish.wait()
        journal.append('signal', {'completed': stem})

    async def wait():
        waiting.set()
        await resume.wait()

    graph = compose_daemon_dispatch(config, work, pause=pause, wait_for_control=wait)
    graph.scheduler.offer(['first', 'second'])
    await started.wait()
    send('pause')
    assert not await pause.allow_offer()
    finish.set()
    await waiting.wait()
    assert calls == ['first'] and len(snapshots) == 1
    assert graph.admission._active is None
    assert any(e.body.get('completed') == 'first' for e in journal.read())
    send('release', hold_id=pause.hold_id)
    resume.set()
    await graph.scheduler.join()
    assert calls == ['first', 'second'] and len(snapshots) == 2


async def test_decision_precedes_hold_mutation_and_duplicate_is_idempotent(boundary, monkeypatch):
    pause, journal, send = boundary
    original = pause._apply
    probes = []

    async def probe(request):
        events = [e for e in journal.read() if e.key == f'control/{request.request_id}']
        assert events[-1].body['outcome'] == 'accepted'
        assert not events[-1].body['applied']
        probes.append((request.action, pause.hold_id))
        await original(request)

    monkeypatch.setattr(pause, '_apply', probe)
    request = send('pause')
    assert not await pause.allow_offer()
    hold = pause.hold_id
    send('pause', request_id=request.request_id)
    assert not await pause.allow_offer() and pause.hold_id == hold
    send('release', hold_id=hold)
    assert await pause.allow_offer()
    assert probes == [('pause', None), ('release', hold)]


async def test_latest_consumed_pause_supersedes_hold_and_only_matching_release_wins(boundary):
    pause, journal, send = boundary
    send('release', hold_id=uuid4())
    send('pause', lifecycle=uuid4())
    assert await pause.allow_offer()
    send('pause')
    assert not await pause.allow_offer()
    old = pause.hold_id
    send('pause')
    assert not await pause.allow_offer()
    current = pause.hold_id
    assert current != old and pause.inbox.holds == {current}
    send('release', hold_id=old)
    send('release', hold_id=current, lifecycle=uuid4())
    assert not await pause.allow_offer() and pause.hold_id == current
    send('release', hold_id=current)
    assert await pause.allow_offer()
    send('pause')
    assert not await pause.allow_offer()
    send('release', hold_id=current)
    assert not await pause.allow_offer()
    assert sum(e.body.get('outcome') == 'stale' for e in journal.read()) == 5


def test_pause_requires_an_explicit_waiter(boundary):
    pause, _, _ = boundary
    with pytest.raises(ValueError, match='wait_for_control'):
        compose_daemon_dispatch(config, None, pause=pause)


def test_production_composition_keeps_pause_dormant(checkout, monkeypatch):
    import squatch.__main__ as cli
    original_drain = cli.Drain
    original_dispatch = cli.compose_daemon_dispatch
    drains, graphs = [], []

    def capture_drain(**kwargs):
        assert kwargs.get('pause') is None
        instance = original_drain(**kwargs)
        drains.append(instance)
        return instance

    def capture_dispatch(*args, **kwargs):
        graph = original_dispatch(*args, **kwargs)
        graphs.append(graph)
        return graph

    monkeypatch.setattr(cli, 'Drain', capture_drain)
    monkeypatch.setattr(cli, 'compose_daemon_dispatch', capture_dispatch)
    assert main(['drain'], cwd=checkout, env=git_env(checkout.parent), out=StringIO()) == 0
    assert len(drains) == len(graphs) == 1
    assert drains[0]._pause is None and graphs[0].pause is None
    with Journal(checkout / 'control-test', clock=lambda: T0) as journal:
        inbox = compose_daemon_control(state_dir=checkout / 'control-test', journal=journal,
                                       fs=LocalFilesystem())
        assert inbox.holds == frozenset()


@pytest.mark.parametrize('release_first', [False, True])
async def test_one_inbox_pass_obeys_latest_pause_release_order(boundary, release_first):
    pause, _, send = boundary
    send('pause')
    assert not await pause.allow_offer()
    old = pause.hold_id
    actions = ['release', 'pause'] if release_first else ['pause', 'release']
    for index, action in enumerate(actions, start=1):
        send(action, request_id=UUID(int=index),
             **({'hold_id': old} if action == 'release' else {}))
    assert not await pause.allow_offer()
    assert pause.hold_id != old and pause.inbox.holds == {pause.hold_id}
    send('release', hold_id=pause.hold_id)
    assert await pause.allow_offer()
