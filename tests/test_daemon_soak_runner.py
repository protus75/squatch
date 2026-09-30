"""The bounded deterministic runner over the production serve composition."""

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from eval.daemon_soak import run
from squatch.artifacts import DAEMON_SOAK_MEMBERS, DAEMON_SOAK_REPORT, DaemonSoakReport
from squatch.audit import audit_journal
from squatch.box import Box
from squatch.journal import read_events, read_segments
from squatch.merge import Merge, Pipeline
from squatch.mergequeue import MergeQueue
from squatch.rework import Rework
from squatch.seams import LocalFilesystem
from squatch.serve import Serve, ServeGraph
from squatch.stages import Stages
from squatch.triage import Triage

ROOT = Path(__file__).resolve().parent.parent
STEMS = {
    "worker_killed_mid_run": "worker-killed-mid-run",
    "conflict_resolution_rungs": "conflict-resolution-rungs",
    "semantic_conflict_integration_red": "semantic-conflict-integration-red",
}


class Clock:
    def __init__(self):
        self.now = datetime(2026, 9, 27, tzinfo=timezone.utc)
        self.advances = []

    def __call__(self):
        return self.now

    def advance(self, elapsed):
        self.advances.append(elapsed)
        self.now += elapsed


class Filesystem(LocalFilesystem):
    def __init__(self):
        self.writes = []

    def write(self, path, data):
        self.writes.append(Path(path))
        super().write(path, data)


@pytest.fixture(scope="module")
def completed_soak(tmp_path_factory):
    evidence = tmp_path_factory.mktemp("daemon-soak")
    clock, fs, graphs, routed = Clock(), Filesystem(), [], []
    active = []
    original = Serve.compose
    original_pipeline_run = Pipeline.run
    original_daemon_admit = Merge.admit_daemon

    def observe(self, session):
        graph = original(self, session)
        graphs.append(graph)
        return graph

    async def pipeline_run(self, ticket, *, run_seq):
        active.append((ticket.stem, run_seq))
        try:
            return await original_pipeline_run(self, ticket, run_seq=run_seq)
        finally:
            active.pop()

    async def daemon_admit(self, ticket, delivery, *, run_seq, queue):
        assert active[-1] == (ticket.stem, run_seq)
        routed.append((ticket.stem, run_seq, queue))
        return await original_daemon_admit(
            self, ticket, delivery, run_seq=run_seq, queue=queue)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(Serve, "compose", observe)
    monkeypatch.setattr(Pipeline, "run", pipeline_run)
    monkeypatch.setattr(Merge, "admit_daemon", daemon_admit)
    try:
        report = run(repo=ROOT, evidence_root=evidence, clock=clock, fs=fs)
    finally:
        monkeypatch.undo()
    return report, evidence, clock, fs, tuple(graphs), tuple(routed)


def local_events(evidence, member):
    return tuple(read_events(evidence / member / ".state"))


def conflict_event(events):
    return next(event for event in events
                if event.body.get("kind") == "merge_conflict_facts")


def main_head(repo):
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "main"], check=True,
        capture_output=True, text=True).stdout.strip()


def commit_named(repo, subject):
    return subprocess.run(
        ["git", "-C", str(repo), "log", "--format=%H", "--grep", f"^{subject}$"],
        check=True, capture_output=True, text=True).stdout.strip()


def changes_since(repo, revision):
    return subprocess.run(
        ["git", "-C", str(repo), "diff", "--name-only", revision, "main"],
        check=True, capture_output=True, text=True).stdout.splitlines()


def lifecycle_durations(events):
    starts = {
        event.body["lifecycle"]: datetime.fromisoformat(event.ts)
        for event in events if event.body.get("kind") == "control_lifecycle"
    }
    stopped = [event for event in events
               if event.body.get("kind") == "control_decision"
               and event.body.get("applied") is True]
    return tuple(datetime.fromisoformat(event.ts)
                 - starts[event.body["request"]["lifecycle"]] for event in stopped)


def passed_invoice(events, step, stem, run_seq):
    event = next(event for event in reversed(events)
                 if event.type == "effect_completion" and event.key is not None
                 and (event.key.startswith(f"{step}/{stem}/{run_seq}/")
                      if step == "regate" else event.key == f"{step}/{stem}/{run_seq}"))
    result = event.body["result"]
    invoice = result["invoice"] if step == "check" else result
    if step == "regate":
        assert event.key == f"regate/{stem}/{run_seq}/{invoice['base']}"
    return not any(check["verdict"] == "fail" and check["severity"] == "hard"
                   for check in invoice["checks"])


def test_runner_drives_exact_members_through_live_production_serve_for_24_hours(
        completed_soak):
    report, evidence, clock, fs, graphs, routed = completed_soak

    assert isinstance(report, DaemonSoakReport)
    assert tuple(entry.member for entry in report.entries) == DAEMON_SOAK_MEMBERS
    assert {path.name for path in evidence.iterdir()} == set(DAEMON_SOAK_MEMBERS)
    assert report.injected_hours == 24
    assert clock.advances == [timedelta(hours=1)] * (24 * 4)
    assert len(graphs) == 4 and all(isinstance(graph, ServeGraph) for graph in graphs)
    assert all(isinstance(graph.pipeline, Pipeline)
               and isinstance(graph.pipeline.stages, Stages)
               and isinstance(graph.pipeline.merge_queue, MergeQueue)
               for graph in graphs)
    assert all(isinstance(graph.rework, Rework) and isinstance(graph.triage, Triage)
               for graph in graphs)
    assert all(graph.stopped.is_set() for graph in graphs)
    assert [(stem, run_seq) for stem, run_seq, _queue in routed] == [
        (STEMS["worker_killed_mid_run"], 1),
        (STEMS["conflict_resolution_rungs"], 0),
        (STEMS["semantic_conflict_integration_red"], 0),
    ]
    assert all(queue is graph.pipeline.merge_queue
               for (_stem, _run_seq, queue), graph in zip(routed, graphs[1:]))
    assert not any(path.name == DAEMON_SOAK_REPORT for path in fs.writes)

    for member in DAEMON_SOAK_MEMBERS:
        member_events = local_events(evidence, member)
        expected_lifecycles = 2 if member == "worker_killed_mid_run" else 1
        durations = lifecycle_durations(member_events)
        assert durations == (timedelta(hours=24),) * expected_lifecycles
        # The age-triggered journal roll is the production daily cadence.  It
        # fires once in every lifecycle rather than being inferred by pooling
        # timestamps from independent scenario repositories.
        segments = tuple(read_segments(evidence / member / ".state"))
        assert len(segments) >= expected_lifecycles + 1


def test_every_closed_field_comes_from_its_member_local_production_evidence(
        completed_soak):
    report, evidence, _clock, _fs, _graphs, _routed = completed_soak
    by_member = {entry.member: entry for entry in report.entries}
    local = {member: local_events(evidence, member) for member in DAEMON_SOAK_MEMBERS}

    worker = by_member["worker_killed_mid_run"]
    abandoned = next(event for event in local[worker.member]
                     if event.body.get("to") == "abandoned")
    alert = next(event for event in local[worker.member]
                 if event.body.get("kind") == "recovery_alert")
    rerun = next(event for event in local[worker.member]
                 if event.body.get("to") == "merged"
                 and event.body.get("run_seq") == 1)
    assert worker.observed == (
        f"{alert.body['kind']}:{abandoned.body['to']}->{rerun.body['to']};"
        f"redispatched={rerun.body['run_seq']}")
    assert alert.body == {
        "kind": "recovery_alert", "run_seq": 0, "disposition": "alert",
        "outcome": "abandoned", "reason": "orphan reaped during entry reconciliation",
    }
    assert worker.disposition == "alert"
    assert worker.producing_run == f"{alert.ticket}/{alert.body['run_seq']}"
    assert passed_invoice(local[worker.member], "check", rerun.ticket, 1)
    assert passed_invoice(local[worker.member], "regate", rerun.ticket, 1)
    assert any(event.key and f"llm/{rerun.ticket}/1/review/" in event.key
               and event.type == "effect_completion" for event in local[worker.member])
    assert any(event.key == f"git/{rerun.ticket}/1/push"
               and event.type == "effect_completion" for event in local[worker.member])
    assert Box(
        evidence / worker.member / ".state", fs=LocalFilesystem(), clock=Clock()
    ).by_origin(rerun.ticket) is None

    conflict = by_member["conflict_resolution_rungs"]
    conflict_facts = conflict_event(local[conflict.member])
    assert conflict_facts.body["strategy_hits"] == [
        {"path": "shared.txt", "strategy": "union"}]
    assert conflict_facts.body["paths"] == ["shared.txt", "manual.txt"]
    assert conflict_facts.body["rung"] == "rework"
    assert conflict.observed == "mechanical->rework;main=green"
    assert conflict.producing_run == (
        f"{conflict_facts.ticket}/{conflict_facts.key.rsplit('/', 1)[1]}")
    assert passed_invoice(local[conflict.member], "check", conflict_facts.ticket, 0)
    conflict_repo = evidence / conflict.member
    conflict_main = commit_named(conflict_repo, "advance main into both conflicts")
    assert main_head(conflict_repo) != conflict_main
    conflict_changes = changes_since(conflict_repo, conflict_main)
    assert conflict_changes and all(path.startswith("tickets/") for path in conflict_changes)

    semantic = by_member["semantic_conflict_integration_red"]
    semantic_facts = conflict_event(local[semantic.member])
    semantic_run = int(semantic_facts.key.rsplit("/", 1)[1])
    semantic_terminal = next(
        event for event in local[semantic.member]
        if event.type == "state_transition" and event.body.get("to") == "gate_failed"
        and event.body.get("run_seq") == semantic_run)
    assert semantic.observed == (
        "integration_red:" + ",".join(semantic_terminal.body["finding_codes"])
        + ";main=green")
    assert semantic.producing_run == f"{semantic_facts.ticket}/{semantic_run}"
    assert passed_invoice(local[semantic.member], "check", semantic_facts.ticket, semantic_run)
    assert passed_invoice(local[semantic.member], "regate", semantic_facts.ticket, semantic_run)
    semantic_repo = evidence / semantic.member
    semantic_main = commit_named(semantic_repo, "advance main before integration")
    assert main_head(semantic_repo) != semantic_main
    semantic_changes = changes_since(semantic_repo, semantic_main)
    assert semantic_changes and all(path.startswith("tickets/") for path in semantic_changes)

    for entry in report.entries:
        state = evidence / entry.member / ".state"
        events = local[entry.member]
        stem, raw_seq = entry.producing_run.rsplit("/", 1)
        run_seq = int(raw_seq)
        running = next(event for event in events
                       if event.ticket == stem and event.body.get("to") == "running"
                       and event.body.get("run_seq") == run_seq)
        assert running, "the production runner, not the soak harness, allocated this run"
        message = Box(state, fs=LocalFilesystem(), clock=Clock()).by_origin(stem)
        if entry.disposition == "box":
            assert message is not None and message.run_seq == run_seq
        else:
            assert message is None
            kind = "recovery_alert" if entry.member == "worker_killed_mid_run" else "escalation"
            assert any(event.ticket == stem and event.body.get("kind") == kind
                       and event.body.get("run_seq") == run_seq for event in events)
        assert any(event.key and f"llm/{stem}/{run_seq}/review/" in event.key
                   and event.type == "effect_completion" for event in events
                   ) == (entry.member != "worker_killed_mid_run")
        assert entry.auditor == ("red" if audit_journal(state) else "green")
        assert entry.green == (entry.observed == entry.expected
                               and entry.auditor == "green")
        other_events = [event for member, events in local.items()
                        if member != entry.member for event in events]
        assert not any(event.ticket == stem and event.body.get("run_seq") == run_seq
                       for event in other_events)


def test_passed_invoice_uses_latest_candidate_base_regate_identity():
    from types import SimpleNamespace
    from eval.daemon_soak import _passed_invoice
    from squatch.journal import Event

    def invoice(base, verdict):
        return Event(1, "effect_completion", "2026-09-29T00:00:00+00:00",
                     "candidate", f"regate/candidate/2/{base}",
                     {"result": {"base": base, "checks": [
                         {"verdict": verdict, "severity": "hard"}]}})

    green = invoice("a" * 40, "pass")
    red = invoice("b" * 40, "fail")
    evidence = SimpleNamespace(events=(green,))
    assert _passed_invoice(evidence, "regate", "candidate", 2)
    evidence.events = (green, red)
    assert not _passed_invoice(evidence, "regate", "candidate", 2)
    assert not _passed_invoice(evidence, "regate", "candidate", 3)
    evidence.events += (invoice("c" * 40, "pass"),)
    assert _passed_invoice(evidence, "regate", "candidate", 2)
