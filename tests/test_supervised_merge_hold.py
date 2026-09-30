"""The daemon's green-before-main supervised admission boundary."""

import asyncio
import json
from io import StringIO
from uuid import uuid4

import pytest

from test_merge import (BOTH, STEM, Agent, Harness, SettledStages, branch_exists,
                        commit_on_main, composed_pipeline_of, deliver, git, ticket_of)
from test_stages import WIDGET, answer, env, implementer, repo, review  # noqa: F401

from squatch.__main__ import main
from squatch.caps import consume, fold as cap_fold
from squatch.config import load
from squatch.control import ControlRequest, publish_control, supervised_merge_holds
from squatch.drain import Drain, Plane, fold
from squatch.diagnose import DiagnosisRecord
from squatch.effects import run_sequence
from squatch.enginelog import EngineLog
from squatch.lockfile import Lockfile
from squatch.ladder import Rung
import squatch.runner as runner_module
from squatch.git import Git
from squatch.journal import Journal, read_events
from squatch.redact import Redactor
from squatch.runner import Refusal, Runner
from squatch.seams import LocalFilesystem, SubprocessExec


async def test_held_custody_survives_restart_and_confirm_regates_moved_main(repo, env):
    h = Harness(repo, env, Agent(answer("implemented"), review("approve"),
                                 actions=[implementer(env, WIDGET)]))
    delivery = await deliver(h)
    main_before = git(repo, env, "rev-parse", "main").strip()
    async def unexpected_release(*_args):
        raise AssertionError("initial admission must hold instead of releasing")

    pipeline = composed_pipeline_of(
        h, supervised=True, release_terminal=unexpected_release)
    pipeline.stages = SettledStages(delivery)
    pipeline.select_daemon_admission()
    order = []
    regate, integration = pipeline.merge_queue._regate, pipeline.merge_queue._integration_check

    async def observed_regate(candidate):
        findings = await regate(candidate)
        assert not supervised_merge_holds(h.journal.read())
        order.append("merge-safety")
        return findings

    async def observed_integration(candidate):
        findings = await integration(candidate)
        assert not supervised_merge_holds(h.journal.read())
        order.append("integration")
        return findings

    pipeline.merge_queue._regate = observed_regate
    pipeline.merge_queue._integration_check = observed_integration

    runner = runner_of(h, lambda _journal: pipeline)
    result = await runner.dispatch(ticket_of(h), h.journal)

    holds = supervised_merge_holds(h.journal.read())
    hold = holds[STEM]
    assert result.held and not result.settled and result.outcome == "ok"
    assert order == ["merge-safety", "integration"]
    assert git(repo, env, "rev-parse", "main").strip() == main_before
    assert branch_exists(h) and h.worktree().is_dir()
    assert run_sequence(h.journal, STEM) == 0
    facts = fold(h.journal.read())
    assert facts.held_admissions == {STEM}
    drain = Drain(runner=runner, repo=repo, config=h.config, git=h.git,
                  clock=h.clock, process=SubprocessExec(), env=env, report=lambda _: None,
                  carried=(STEM,))
    plane = Plane({STEM: ticket_of(h)}, {}, ())
    assert drain._eligible(plane, facts) == []
    assert drain._reoffers(plane, facts) == []
    with pytest.raises(Refusal, match="held for supervised merge"):
        runner._eligible(ticket_of(h), h.journal)
    assert not any(event.type == "state_transition" and event.body.get("to") == "merged"
                   for event in h.journal.read())

    stale = await pipeline.control_inbox.confirm(STEM, uuid4(), actor="operator")
    assert stale.outcome == "stale"
    assert supervised_merge_holds(h.journal.read())[STEM] == hold
    h.journal.close()

    moved = commit_on_main(h, "squatch/existing.py", "EXISTING = 2\n", "main moved")
    out = StringIO()
    assert await asyncio.to_thread(
        main, ["confirm", STEM], cwd=repo, env=env, out=out, clock=h.clock) == 0, out.getvalue()

    events = tuple(read_events(h.state))
    assert not supervised_merge_holds(events)
    assert not any(event.type == "state_transition" and event.body.get("to") == "abandoned"
                   for event in events)
    assert [event.body["actor"] for event in events
            if event.body.get("kind") == "supervised_merge_release"] == ["operator"]
    assert not any(event.body.get("kind") == "confirm" for event in events)
    regates = [event for event in events if event.type == "effect_completion"
               and event.key.startswith(f"regate/{STEM}/0/")]
    assert [event.body["result"]["base"] for event in regates] == [main_before, moved]
    assert [event.key for event in regates] == [
        f"regate/{STEM}/0/{main_before}", f"regate/{STEM}/0/{moved}"]
    assert git(repo, env, "merge-base", "--is-ancestor", moved, "main").strip() == ""
    assert "squatch/widget.py" in git(repo, env, "ls-tree", "-r", "--name-only", "main")
    assert not branch_exists(h) and not h.worktree().exists()


async def test_bootstrap_pipeline_never_holds(repo, env):
    h = Harness(repo, env, Agent(answer("implemented"), review("approve"),
                                 actions=[implementer(env, WIDGET)]))
    delivery = await deliver(h)
    pipeline = composed_pipeline_of(h)
    pipeline.stages = SettledStages(delivery)

    result = await pipeline.run(ticket_of(h), run_seq=0)

    assert pipeline.admission_mode == "inline"
    assert result.admission_state == "SETTLED"
    assert not supervised_merge_holds(h.journal.read())
    assert not branch_exists(h) and not h.worktree().exists()


@pytest.mark.parametrize("conflict", [False, True])
async def test_release_failure_retires_hold_and_uses_terminal_harvest(repo, env, conflict):
    h = Harness(repo, env, Agent(
        answer("implemented"), review("approve"),
        actions=[implementer(env, WIDGET)]))
    delivery = await deliver(h, verify=BOTH)
    h.journal.append("state_transition", {"to": "running", "run_seq": 0}, ticket=STEM)
    runner = None

    async def unexpected_release(*_args):
        raise AssertionError("initial admission must hold instead of releasing")

    pipeline = composed_pipeline_of(
        h, supervised=True, release_terminal=unexpected_release)
    pipeline.stages = SettledStages(delivery)
    pipeline.select_daemon_admission()
    held = await pipeline.run(ticket_of(h), run_seq=0)
    assert held.admission_state == "HELD"
    h.journal.close()
    main_before = commit_on_main(
        h, "squatch/widget.py" if conflict else "squatch/existing.py",
        "WIDGET = 2\n" if conflict else "EXISTING = 2\n", "main moved")
    config = load(None, cwd=repo)

    def factory(journal):
        async def release_terminal(ticket, released, composed, run_seq):
            await runner.finish_release(
                ticket, released, journal, composed, run_seq=run_seq)

        composed = composed_pipeline_of(
            h, journal=journal, supervised=False, release_terminal=release_terminal)

        async def diagnose(ticket, delivery, *, run_seq):
            return DiagnosisRecord(run_seq=run_seq, outcome=delivery.outcome, call="ok",
                                   verdict="retry", lessons=("recheck moved main",),
                                   reason="retry", detail=None)

        composed.diagnose = diagnose
        return composed

    runner = Runner(
        repo=repo, config=config, git=Git(SubprocessExec(), env=env, timeout=60),
        fs=LocalFilesystem(), clock=h.clock, instance_id="restart", pipeline=factory,
        log=EngineLog(h.state, clock=h.clock, redact=Redactor.from_config(config, env)),
        report=lambda _line: None)

    assert await runner.confirm(STEM) == 0

    events = tuple(read_events(h.state))
    assert not supervised_merge_holds(events)
    terminal = [event.body for event in events
                if event.type == "state_transition" and event.ticket == STEM][-1]
    assert terminal["to"] == "gate_failed"
    assert terminal["harvest"] == f"tickets/{STEM}/attempts/0"
    assert (repo / terminal["harvest"] / "harvest.json").is_file()
    assert git(repo, env, "merge-base", "--is-ancestor", main_before, "main").strip() == ""
    if conflict:
        assert git(repo, env, "show", "main:squatch/widget.py") == "WIDGET = 2\n"
        assert any(event.body.get("rung") == "rework" for event in events)
    else:
        assert "squatch/widget.py" not in git(
            repo, env, "ls-tree", "-r", "--name-only", "main")
    assert branch_exists(h) and not h.worktree().exists()
    with Journal(h.state, clock=h.clock) as journal:
        runner._eligible(ticket_of(h), journal)
        drain = Drain(runner=runner, repo=repo, config=config, git=h.git,
                      clock=h.clock, process=SubprocessExec(), env=env, report=lambda _: None)
        plane = Plane({STEM: ticket_of(h)}, {}, ())
        assert [ticket.stem for ticket in drain._reoffers(plane, fold(journal.read()))] == [STEM]


def runner_of(h, factory):
    return Runner(
        repo=h.repo, config=h.config, git=h.git, fs=LocalFilesystem(), clock=h.clock,
        instance_id="supervised-test", pipeline=factory,
        log=EngineLog(h.state, clock=h.clock, redact=Redactor.from_config(h.config, h.env)),
        report=lambda _line: None)


@pytest.mark.parametrize("actor", ["operator", "machine"])
async def test_live_confirm_binds_identity_and_preserves_caps(repo, env, actor):
    h = Harness(repo, env, Agent(answer("implemented"), review("approve"),
                                 actions=[implementer(env, WIDGET)]))
    delivery = await deliver(h)

    async def unexpected_release(*_args):
        raise AssertionError("green release must not route a failure")

    pipeline = composed_pipeline_of(h, supervised=True, release_terminal=unexpected_release)
    pipeline.stages = SettledStages(delivery)
    pipeline.select_daemon_admission()
    assert (await pipeline.run(ticket_of(h), run_seq=0)).admission_state == "HELD"
    hold = supervised_merge_holds(h.journal.read())[STEM]
    inbox = pipeline.control_inbox
    await consume(h.journal, repo=repo, git=h.git, stem=STEM, cap="retry", run_seq=0)
    caps = cap_fold(h.journal.read()).counts

    async def no_mutation(_request):
        return None

    for request in (
            ControlRequest(action="confirm", lifecycle=uuid4(), hold_id=hold.hold_id,
                           stem=STEM, actor=actor),
            ControlRequest(action="confirm", lifecycle=inbox.lifecycle, hold_id=uuid4(),
                           stem=STEM, actor=actor),
            ControlRequest(action="confirm", lifecycle=inbox.lifecycle, hold_id=hold.hold_id,
                           stem="another-stem", actor=actor),
            ControlRequest(action="release", lifecycle=inbox.lifecycle, hold_id=hold.hold_id)):
        publish_control(h.state, request, LocalFilesystem())
        [decision] = await inbox.consume(no_mutation)
        assert decision.outcome in {"stale", "invalid"}
        assert supervised_merge_holds(h.journal.read())[STEM] == hold
        assert h.worktree().is_dir()

    lock = Lockfile(h.state, instance_id="live", clock=h.clock)
    lock.acquire()
    try:
        h.journal.append("signal", {
            "kind": "control_lifecycle", "lifecycle": str(inbox.lifecycle),
            "holder": json.loads(lock.path.read_text())})
        before = tuple(h.journal.read())
        if actor == "operator":
            out = StringIO()
            assert await asyncio.to_thread(
                main, ["confirm", STEM], cwd=repo, env=env, out=out, clock=h.clock) == 0
            assert "published confirm" in out.getvalue()
        else:
            publish_control(h.state, ControlRequest(
                action="confirm", lifecycle=inbox.lifecycle, hold_id=hold.hold_id,
                stem=STEM, actor=actor), LocalFilesystem())
        assert tuple(h.journal.read()) == before
        [decision] = await inbox.consume(no_mutation)
        assert decision.outcome == "accepted" and decision.applied
        assert not supervised_merge_holds(h.journal.read())
        assert not h.worktree().exists()
        events = tuple(h.journal.read())
        assert cap_fold(events).counts == caps
        assert not any(event.body.get("kind") == "confirm" for event in events)
        release = next(event for event in events
                       if event.body.get("kind") == "supervised_merge_release")
        assert release.body["actor"] == actor
        accepted = next(event for event in events
                        if event.body.get("kind") == "control_decision"
                        and event.body["outcome"] == "accepted")
        assert events.index(accepted) < events.index(release)
        assert (await inbox.confirm(STEM, hold.hold_id, actor=actor)).outcome == "stale"
    finally:
        lock.release()


async def test_terminal_routing_uses_the_effective_escalated_rung(repo, env, monkeypatch):
    from dataclasses import replace
    from squatch.reject import Routing

    h = Harness(repo, env, Agent(answer("implemented"), review("approve"),
                                 actions=[implementer(env, WIDGET)]))
    delivery = await deliver(h)
    await consume(h.journal, repo=repo, git=h.git, stem=STEM, cap="retry", run_seq=0,
                  rung={"tier": "high", "effort": "high"})
    routed = []

    def route(*_args, current, delivery):
        routed.append(current)
        return Routing(None, None)

    class FailedPipeline:
        async def diagnose(self, ticket, delivery, *, run_seq):
            return DiagnosisRecord(run_seq=run_seq, outcome="gate_failed", call="ok",
                                   verdict="retry", lessons=("retry",), reason="retry",
                                   detail=None)

    monkeypatch.setattr(runner_module, "route", route)
    runner = runner_of(h, lambda _journal: FailedPipeline())
    await runner.finish_release(
        ticket_of(h), replace(delivery, outcome="gate_failed"), h.journal,
        FailedPipeline(), run_seq=0)
    assert routed == [Rung("high", "high")]
