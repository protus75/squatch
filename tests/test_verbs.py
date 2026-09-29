"""Operator verdict verbs over the lock-held journal identity."""

from io import StringIO

import pytest

from test_cli import STATE, T0, checkout, git_env  # noqa: F401
from test_drain import FakeClock, Scripted, committed, drain, git

import squatch.__main__ as main_module
from squatch.__main__ import main
from squatch.box import Box
from squatch.doctor import Check, Report
from squatch.journal import Journal, read_events
from squatch.lockfile import LockHeld, Lockfile
from squatch.runner import EXIT_OK, EXIT_REFUSED
from squatch.seams import LocalFilesystem
from squatch.tickets import stamp


def verdict(checkout, verb: str, stem: str, *, pipeline=None):
    out = StringIO()
    rc = main([verb, stem], cwd=checkout, env=git_env(checkout.parent), out=out,
              pipeline=pipeline, clock=FakeClock())
    return rc, out.getvalue()


def test_operator_verb_surface_includes_provider_free_doctor_and_manual_retro():
    parser = main_module._parser()
    subparsers = next(action for action in parser._actions
                      if hasattr(action, "choices") and action.choices)
    assert {"doctor", "retro"} <= set(subparsers.choices)


def test_doctor_dispatches_without_pipeline_provider_or_writer_lock(
        checkout, monkeypatch):
    calls = []

    class RecordingDoctor:
        def __init__(self, **kwargs):
            calls.append(("init", kwargs))

        async def run(self):
            calls.append(("run",))
            return Report(tuple(Check(name, True, "ok") for name in (
                "venv", "git", "config", "lock", "journal")))

    def forbidden_pipeline(_journal):
        raise AssertionError("doctor constructed a pipeline or provider session")

    monkeypatch.setattr(main_module, "Doctor", RecordingDoctor)
    holder = Lockfile(checkout / STATE, instance_id="live-engine", clock=FakeClock())
    holder.acquire()
    try:
        out = StringIO()
        rc = main(["doctor"], cwd=checkout, env=git_env(checkout.parent), out=out,
                  pipeline=forbidden_pipeline, clock=FakeClock())
    finally:
        holder.release()

    assert rc == EXIT_OK
    assert out.getvalue().startswith("doctor: ok\n")
    assert [call[0] for call in calls] == ["init", "run"]


def test_manual_retro_dispatches_under_lock_with_manual_forced_contract(
        checkout, monkeypatch):
    with Journal(checkout / STATE, clock=FakeClock()) as journal:
        journal.append("state_transition", {"to": "merged"}, ticket="feature")
    scripted = Scripted({})
    captured = {}

    class RecordingRetro:
        def __init__(self, **kwargs):
            captured["init"] = kwargs

        async def run(self, trigger, *, forced):
            captured["run"] = (trigger, forced)
            probe = Lockfile(checkout / STATE, instance_id="probe", clock=FakeClock())
            with pytest.raises(LockHeld):
                probe.acquire()
            return False

    monkeypatch.setattr(main_module, "Retro", RecordingRetro)
    out = StringIO()
    rc = main(["retro"], cwd=checkout, env=git_env(checkout.parent), out=out,
              pipeline=scripted, clock=FakeClock())

    assert rc == 1
    assert captured["run"] == ("manual", True)
    assert captured["init"]["driver"] is scripted.stages.driver
    assert captured["init"]["providers"] is not None


def signal_bodies(checkout, stem: str, *kinds: str):
    return [event.body for event in read_events(checkout / STATE)
            if event.ticket == stem and event.type == "signal"
            and event.body.get("kind") in kinds]


def test_confirm_flips_a_committed_draft_through_the_lane_and_drain_runs_it(checkout):
    path = committed(checkout, "draft-one", signal_at=T0)
    path.write_text(stamp(path.read_text(), state="draft"))
    git(checkout, "commit", "-q", "-am", "draft")

    rc, out = verdict(checkout, "confirm", "draft-one")

    assert rc == EXIT_OK and "moved from draft to confirmed" in out
    committed_text = git(checkout, "show", "HEAD:tickets/draft-one/ticket.md")
    assert "state: confirmed" in committed_text and "source: human" in committed_text
    blob = git(checkout, "rev-parse", "HEAD:tickets/draft-one/ticket.md").strip()
    [body] = signal_bodies(checkout, "draft-one", "confirm")
    assert body["actor"] == "operator" and body["ticket_sha"] == blob

    fake = Scripted({"draft-one": ["ok"]})
    assert drain(checkout, fake)[0] == EXIT_OK
    assert fake.calls == [("draft-one", 0)]


def test_confirm_keep_refuses_the_same_revision_then_accepts_a_committed_edit(checkout):
    path = committed(checkout, "parked", signal_at=T0)
    with Journal(checkout / STATE, clock=FakeClock()) as journal:
        journal.append("state_transition", {"to": "running", "run_seq": 0}, ticket="parked")
        journal.append("state_transition", {"to": "gate_failed", "run_seq": 0},
                       ticket="parked")

    assert verdict(checkout, "confirm", "parked")[0] == EXIT_OK
    rc, out = verdict(checkout, "confirm", "parked")
    assert rc == EXIT_REFUSED
    assert "edit the ticket (or fix the plan and regenerate it) before re-enqueueing" in out

    path.write_text(path.read_text().replace("The widget parser lands.",
                                             "The widget parser lands after the fix."))
    rc, _ = verdict(checkout, "confirm", "parked")
    assert rc == EXIT_OK
    confirms = signal_bodies(checkout, "parked", "confirm")
    assert len(confirms) == 2 and confirms[0]["ticket_sha"] != confirms[1]["ticket_sha"]


def test_confirm_refuses_a_confirmed_never_run_stem_without_writing(checkout):
    committed(checkout, "idle", signal_at=T0)
    before = list(read_events(checkout / STATE))

    rc, out = verdict(checkout, "confirm", "idle")

    assert rc == EXIT_REFUSED
    assert "confirmed and has never run" in out and "nothing is parked" in out
    assert list(read_events(checkout / STATE)) == before


def test_verdicts_require_journal_identity_and_refuse_merged_stems(checkout):
    for verb in ("confirm", "reject"):
        rc, out = verdict(checkout, verb, "ghost")
        assert rc == EXIT_REFUSED and "no journal identity; intake or author it first" in out

    committed(checkout, "done", signal_at=T0)
    with Journal(checkout / STATE, clock=FakeClock()) as journal:
        journal.append("state_transition", {"to": "merged", "run_seq": 0}, ticket="done")
    for verb in ("confirm", "reject"):
        rc, out = verdict(checkout, verb, "done")
        assert rc == EXIT_REFUSED and "already merged" in out


def test_verdicts_refuse_an_already_rejected_stem_without_writing(checkout):
    committed(checkout, "killed", signal_at=T0)
    with Journal(checkout / STATE, clock=FakeClock()) as journal:
        journal.append("state_transition", {"to": "rejected", "run_seq": 0}, ticket="killed")
    before = list(read_events(checkout / STATE))

    for verb in ("confirm", "reject"):
        rc, out = verdict(checkout, verb, "killed")
        assert rc == EXIT_REFUSED and "already rejected" in out
        assert list(read_events(checkout / STATE)) == before


def test_reject_a_dirless_identity_is_journal_only(checkout):
    committed(checkout, "gone", signal_at=T0)
    git(checkout, "rm", "-q", "tickets/gone/ticket.md")
    git(checkout, "commit", "-q", "-m", "remove gone")

    assert verdict(checkout, "reject", "gone")[0] == EXIT_OK
    events = [event for event in read_events(checkout / STATE) if event.ticket == "gone"]
    reject = next(event for event in events
                  if event.type == "signal" and event.body.get("kind") == "reject")
    transition = next(event for event in events
                      if event.type == "state_transition" and event.body.get("to") == "rejected")
    assert reject.body["ticket_sha"] is None and transition.body["to"] == "rejected"


def test_reject_stamps_and_reports_each_committed_direct_dependent(checkout):
    committed(checkout, "dead", signal_at=T0)
    committed(checkout, "child-a", depends="dead", signal_at=T0)
    committed(checkout, "child-b", depends="dead", signal_at=T0)
    with Journal(checkout / STATE, clock=FakeClock()) as journal:
        journal.append("state_transition", {"to": "gate_failed", "run_seq": 0}, ticket="dead")

    rc, out = verdict(checkout, "reject", "dead")

    assert rc == EXIT_OK and "2 dependent(s) reported" in out
    assert "state: rejected" in git(checkout, "show", "HEAD:tickets/dead/ticket.md")
    events = list(read_events(checkout / STATE))
    relevant = [(event.type, event.body.get("kind") or event.body.get("to"))
                for event in events
                if (event.ticket == "dead" and
                    (event.body.get("kind") == "reject" or event.body.get("to") == "rejected"))
                or event.body.get("kind") == "dead_dependency"]
    assert relevant == [("signal", "reject"), ("state_transition", "rejected"),
                        ("signal", "dead_dependency"), ("signal", "dead_dependency")]
    pending = Box(checkout / STATE, fs=LocalFilesystem(), clock=FakeClock()).pending()
    assert {message.origin for message in pending} == {"dead"}
    assert {message.message_class for message in pending} == {"failure_report"}
    assert {"child-a", "child-b"} == {
        name for name in ("child-a", "child-b")
        if any(name in message.summary for message in pending)}


def test_reject_an_unstampable_ticket_is_journal_only_and_reports_dependents(checkout):
    path = committed(checkout, "broken", signal_at=T0)
    committed(checkout, "child", depends="broken", signal_at=T0)
    path.write_text("frontmatter fences are gone\n")
    git(checkout, "add", "--", "tickets/broken/ticket.md")
    git(checkout, "commit", "-q", "-m", "break ticket", "--",
        "tickets/broken/ticket.md")

    rc, out = verdict(checkout, "reject", "broken")

    assert rc == EXIT_OK and "1 dependent(s) reported" in out
    events = list(read_events(checkout / STATE))
    relevant = [(event.type, event.body.get("kind") or event.body.get("to"))
                for event in events
                if (event.ticket == "broken" and
                    (event.body.get("kind") == "reject"
                     or event.body.get("to") == "rejected"))
                or event.body.get("kind") == "dead_dependency"]
    assert relevant == [("signal", "reject"), ("state_transition", "rejected"),
                        ("signal", "dead_dependency")]
    assert git(checkout, "show", "HEAD:tickets/broken/ticket.md") == \
        "frontmatter fences are gone\n"
    [message] = Box(checkout / STATE, fs=LocalFilesystem(), clock=FakeClock()).pending()
    assert message.message_class == "failure_report" and message.origin == "broken"
    assert "child" in message.summary and "squatch reject child" in message.detail


def test_both_verbs_refuse_a_held_lock_without_writing(checkout):
    committed(checkout, "parked", signal_at=T0)
    before = list(read_events(checkout / STATE))
    holder = Lockfile(checkout / STATE, instance_id="other", clock=FakeClock())
    holder.acquire()
    try:
        for verb in ("confirm", "reject"):
            assert verdict(checkout, verb, "parked")[0] == EXIT_REFUSED
    finally:
        holder.release()
    assert list(read_events(checkout / STATE)) == before


def test_verdict_verbs_resolve_a_marked_reject_hold(checkout):
    for stem in ("kept", "killed"):
        committed(checkout, stem, signal_at=T0)
        with Journal(checkout / STATE, clock=FakeClock()) as journal:
            journal.append("state_transition", {"to": "gate_failed", "run_seq": 0,
                                                 "routed": "reject_queue",
                                                 "reject_reason": "diagnosis verdict reject"},
                           ticket=stem)
            journal.append("signal", {"kind": "escalation",
                                       "escalation": "reject_queue_arrival",
                                       "reason": "diagnosis verdict reject", "run_seq": 0},
                           ticket=stem)

    assert verdict(checkout, "confirm", "kept")[0] == EXIT_OK
    assert verdict(checkout, "reject", "killed")[0] == EXIT_OK
    fake = Scripted({"kept": ["ok"]})
    assert drain(checkout, fake)[0] == EXIT_OK
    assert fake.calls == [("kept", 1)]

    out = StringIO()
    assert main(["status"], cwd=checkout, env=git_env(checkout.parent), out=out,
                clock=FakeClock()) == EXIT_OK
    assert "reject queue (0)" in out.getvalue()
