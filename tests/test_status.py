"""The deterministic, read-only Phase 5 status projection."""

from dataclasses import fields
from datetime import datetime, timezone
from io import StringIO

from squatch import __main__ as cli_module
from squatch.__main__ import main
from squatch.box import Box
from squatch.journal import Event, Journal
from squatch.retro import Window
from squatch.runner import EXIT_OK, EXIT_REFUSED
from squatch.scorecard import project_scorecard
from squatch.seams import LocalFilesystem
from squatch.status import Status, project, render
from squatch.tickets import TEMPLATE

T0 = datetime(2026, 9, 28, 12, tzinfo=timezone.utc)


def event(kind, body, *, ticket=None, key=None):
    return Event(v=1, type=kind, ts=T0.isoformat(), ticket=ticket, key=key, body=body)


def intake(stem, state="confirmed"):
    return event("signal", {"kind": "ticket_intake", "source": "human", "state": state,
                            "commit": f"{stem}-commit"}, ticket=stem)


def ticket(repo, stem, *, depends="none", text=None):
    path = repo / "tickets" / stem / "ticket.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text((TEMPLATE.replace("- none", f"- {depends}") if text is None else text))


def test_all_preserved_fields_values_renderings_and_deterministic_folds(tmp_path):
    for stem, depends in (("pending", "none"), ("ready", "none"),
                          ("blocked", "missing-dependency"), ("running", "none"),
                          ("stopped", "none"), ("merged", "none"), ("rejected", "none")):
        ticket(tmp_path, stem, depends=depends)
    ticket(tmp_path, "unparsed", text="not a ticket")

    queue = Box(tmp_path / "state", fs=LocalFilesystem(), clock=lambda: T0)
    old = queue.enqueue(message_class="suggestion", summary="old", detail="old", origin="test")
    queue.resolve(old.id, status="tombstoned", link="ticket", note="covered")
    open_message = queue.enqueue(
        message_class="suggestion", summary="open", detail="open", origin="test")

    events = (
        intake("ready"), intake("blocked"), intake("running"), intake("stopped"),
        intake("merged"), intake("rejected"),
        event("state_transition", {"to": "running", "run_seq": 4}, ticket="running"),
        event("state_transition", {"to": "gate_failed", "run_seq": 2}, ticket="stopped"),
        event("state_transition", {"to": "merged", "run_seq": 1}, ticket="merged"),
        event("state_transition", {"to": "gate_failed", "routed": "reject_queue",
                                    "reject_reason": "needs operator", "run_seq": 3},
              ticket="rejected"),
        event("effect_completion", {"cost": {"usd": 1.25}}),
        event("effect_completion", {"cost": {"usd": "bad"}}),
        event("effect_completion", {"cost": {"usd": True}}),
        event("effect_completion", {"cost": "bad"}),
    )
    status = project(events, repo=tmp_path, state_dir=tmp_path / "state")

    assert [field.name for field in fields(Status)] == [
        "unparsed", "pending", "in_flight", "ready", "blocked", "stopped", "merged",
        "intake", "spend_usd", "calls", "box", "reject_queue", "box_activity",
        "tombstone_digest", "scorecard"]
    assert [item.stem for item in status.unparsed] == ["unparsed"]
    assert status.pending == ("pending",)
    assert status.in_flight == (("running", 4),)
    assert status.ready == ("ready", "stopped")
    assert status.blocked == (("blocked", ("missing-dependency",)),)
    assert status.stopped == (("stopped", "gate_failed"),)
    assert status.merged == ("merged",)
    assert tuple(item.stem for item in status.intake) == (
        "blocked", "merged", "ready", "rejected", "running", "stopped")
    assert (status.spend_usd, status.calls) == (1.25, 1)
    assert tuple(message.id for message in status.box) == (open_message.id,)
    assert status.reject_queue[0][0] == "rejected"
    assert status.box_activity == (("pending", 1), ("tombstoned", 1))
    assert status.tombstone_digest == (
        (old.id, queue.get(old.id).signature, 1, False),)

    unparsed = status.unparsed[0]
    rejected = status.reject_queue[0][1]
    text = render(status)
    expected_sections = (
        f"unparsed tickets (failed intake lint) (1)\n  {unparsed.stem}: {unparsed.message} -- "
        f"{unparsed.paved_road}\n",
        "pending intake (1)\n  pending\n",
        "in flight (1)\n  running (run 4)\n",
        "ready (2)\n  ready\n  stopped\n",
        "blocked (1)\n  blocked: waiting on missing-dependency\n",
        f"reject queue (1)\n  rejected: needs operator; arrived {rejected.ts}; "
        "`squatch confirm rejected` to keep or `squatch reject rejected` to kill\n",
        "stopped (1)\n  stopped: gate_failed\n",
        "merged (1)\n  merged\n",
        "intake (6)\n",
        f"box (1)\n  {open_message.id}: suggestion: open\n",
        "spend: $1.2500 over 1 metered calls\n",
    )
    assert all(section in text for section in expected_sections)


def test_latest_terminal_and_latest_unmatched_running_are_independent(tmp_path):
    events = (
        intake("a"), intake("b"),
        event("state_transition", {"to": "merged"}, ticket="a"),
        event("state_transition", {"to": "running", "run_seq": 3}, ticket="a"),
        event("state_transition", {"to": "merged"}, ticket="b"),
        event("state_transition", {"to": "gate_failed"}, ticket="b"),
    )
    status = project(events, repo=tmp_path, state_dir=tmp_path / "state")
    assert status.merged == ("a",)
    assert status.in_flight == (("a", 3),)
    assert status.stopped == (("b", "gate_failed"),)


def test_scorecard_rendering_is_additive_and_absent_when_not_supplied(tmp_path):
    plain = render(project((), repo=tmp_path, state_dir=tmp_path / "state"))
    scorecard = project_scorecard(Window((), T0).projection(sha="head", spec_version="1.0"))
    rendered = render(project((), repo=tmp_path, state_dir=tmp_path / "state",
                              scorecard=scorecard))
    assert "## Surface scorecard" not in plain
    assert "## Surface scorecard\n\n| Surface | Evaluated tickets" in rendered


class HeadProcess:
    def __init__(self, sha="known-head", rc=0):
        self.sha = sha
        self.rc = rc
        self.argv = []

    async def run(self, argv, **_kwargs):
        self.argv.append(argv)
        return self.rc, f"{self.sha}\n" if self.rc == 0 else "", "no head"


def test_production_status_uses_clock_head_and_engine_retro_version_and_excludes_bad_metrics(
        tmp_path, monkeypatch):
    (tmp_path / "config.yaml").write_text(
        "schema_version: 1\nstate_dir: state\nproviders: []\nrouting: []\n")
    with Journal(tmp_path / "state", clock=lambda: T0) as journal:
        journal.append("effect_completion", {
            "cost": {"usd": 2.5, "input_tokens": 7, "output_tokens": 3}, "result": {}},
            key="llm/good")
        for number, cost in enumerate((
                {"usd": "bad", "input_tokens": "bad", "output_tokens": None},
                {"usd": True, "input_tokens": True, "output_tokens": False})):
            journal.append("effect_completion", {"cost": cost, "result": {}},
                           key=f"llm/bad/{number}")

    seen = {}
    real_project = cli_module.project_scorecard

    def capture(window):
        seen["window"] = window
        return real_project(window)

    monkeypatch.setattr(cli_module, "project_scorecard", capture)
    out = StringIO()
    process = HeadProcess()
    assert main(["status"], cwd=tmp_path, env={}, out=out, clock=lambda: T0,
                process=process) == EXIT_OK
    window = seen["window"]
    assert process.argv == [["git", "-C", str(tmp_path), "rev-parse", "--verify", "HEAD"]]
    assert window.produced_at_sha == "known-head"
    assert window.produced_by_spec_version == "1.0"
    assert window.ended_at == T0.isoformat()
    assert (window.spend_usd, window.tokens) == (2.5, 10)
    assert "## Surface scorecard" in out.getvalue()


def test_status_maps_head_and_spec_failures_to_refusals(tmp_path, monkeypatch):
    (tmp_path / "config.yaml").write_text(
        "schema_version: 1\nstate_dir: state\nproviders: []\nrouting: []\n")
    out = StringIO()
    assert main(["status"], cwd=tmp_path, env={}, out=out,
                process=HeadProcess(rc=1)) == EXIT_REFUSED
    assert "cannot resolve HEAD" in out.getvalue() and "paved road" in out.getvalue()

    monkeypatch.setattr(cli_module, "load_spec", lambda _path: (_ for _ in ()).throw(
        OSError("unreadable")))
    out = StringIO()
    assert main(["status"], cwd=tmp_path, env={}, out=out,
                process=HeadProcess()) == EXIT_REFUSED
    assert "cannot load retro spec" in out.getvalue() and "paved road" in out.getvalue()
