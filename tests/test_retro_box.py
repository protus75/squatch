import ast
import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_author import reply, review_reply, setup_author, ticket
from test_cli import STATE, T0, checkout  # noqa: F401 -- fixture
from test_merge import (BASE_RED, GREEN, STEM, TICKET, WIDGET, SettledStages,
                        Agent as MergeAgent, Harness as MergeHarness,
                        answer as merge_answer, deliver as merge_deliver,
                        composed_pipeline_of,
                        env,  # noqa: F401 -- fixture
                        implementer as merge_implementer, merge_of, review as merge_review,
                        repo,  # noqa: F401 -- fixture
                        ticket_of)
from test_retro import Clock, answer, retro

from squatch.box import (REREPORT_PAVED_ROAD, Box, RereportCallbackRequired,
                         ingest, journal_rereport_callback)
from squatch.journal import Event, Journal, read_events
from squatch.llm import FakeLLM
from squatch.merge import Merge
from squatch.registry import Record, write
from squatch.retro import proposal_id
from squatch.seams import LocalFilesystem
from squatch.tickets import Intake
from squatch.triage import Triage, TriageTombstone


def _retro_values(report="retro/000001", fixed="Failure 1", risk="Risk 1",
                  paths=("specs/review.md",)):
    return {
        "retro_report_key": report,
        "fixed_failure": fixed,
        "overcorrection_risk": risk,
        "proposed_spec_paths": paths,
    }


def test_retro_proposal_identity_origin_replay_and_distinctions(tmp_path):
    clock = Clock()
    state = tmp_path / "state"
    with Journal(state, clock=clock) as journal:
        journal.append("state_transition", {"to": "merged"}, ticket="feature")
        value, _repo = retro(tmp_path, journal, clock, FakeLLM(answer()))
        assert asyncio.run(value.run("quiescence", forced=True))

    [message] = Box(state, fs=LocalFilesystem(), clock=clock).pending()
    expected = hashlib.sha256(json.dumps([
        "retro/000001", "A repeated rejection is too vague.",
        "Extra prose could dilute the prompt.", ["specs/review.md"],
    ], ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()[:16]
    assert proposal_id(
        message.retro_report_key, message.fixed_failure, message.overcorrection_risk,
        message.proposed_spec_paths) == expected
    assert message.origin == f"retro-proposal/retro/000001/{expected}"
    assert message.message_class == "retro_finding"

    queue = Box(state, fs=LocalFilesystem(), clock=clock)
    replay = queue.enqueue(
        message_class="retro_finding", summary=message.fixed_failure,
        detail=message.detail, origin=message.origin, stage="retro", outcome="ok",
        **_retro_values(
            fixed=message.fixed_failure, risk=message.overcorrection_risk,
            paths=message.proposed_spec_paths))
    assert replay.duplicate and replay.id == message.id
    identities = {
        proposal_id("retro/000001", "Failure 1", "Risk", ("specs/review.md",)),
        proposal_id("retro/000001", "Failure 2", "Risk", ("specs/review.md",)),
        proposal_id("retro/000001", "Failure 1", "Risk", ("specs/author.md",)),
    }
    assert len(identities) == 3


    ids = []
    for fixed, paths in [("Failure 1", ("specs/review.md",)),
                         ("Failure 2", ("specs/review.md",)),
                         ("Failure 1", ("specs/author.md",))]:
        identity = proposal_id("retro/000001", fixed, "Risk", paths)
        item = queue.enqueue(
            message_class="retro_finding", summary=fixed, detail=f"{fixed} {paths[0]}",
            origin=f"retro-proposal/retro/000001/{identity}",
            **_retro_values(fixed=fixed, risk="Risk", paths=paths))
        assert not item.duplicate
        ids.append(item.id)
    assert len(set(ids)) == 3
    assert proposal_id("retro/000001", "Failure", "Risk", ("specs/z.md", "specs/a.md")) == (
        proposal_id("retro/000001", "Failure", "Risk", ("specs/a.md", "specs/z.md")))


def test_author_is_the_only_production_baseline_reader_caller():
    root = Path(__file__).parents[1] / "squatch"
    callers = []
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "squatch.baseline":
                callers.extend((path.name, alias.name) for alias in node.names)
    assert callers == [("author.py", "resolve_baseline")]


def test_rereport_journals_before_reopen_and_enqueue_uses_shared_route(tmp_path):
    state = tmp_path / "state"
    with Journal(state, clock=lambda: T0) as journal:
        observed = []
        callback = journal_rereport_callback(journal)
        queue = None

        def before_clear(message):
            current = queue.get(message.id)
            observed.append((current.status, current.resolution is not None))
            callback(message)

        queue = Box(state, fs=LocalFilesystem(), clock=lambda: T0,
                    rereport_callback=before_clear)
        first = queue.enqueue(message_class="suggestion", summary="one", detail="same 1",
                              origin="host")
        queue.resolve(first.id, status="tombstoned", link="existing", note="duplicate")
        assert queue.enqueue(message_class="suggestion", summary="two", detail="same 2",
                             origin="host").duplicate
        assert queue.enqueue(message_class="suggestion", summary="three", detail="same 3",
                             origin="host").duplicate
        reopened = queue.get(first.id)
        assert observed == [("tombstoned", True)]
        assert (reopened.status, reopened.resolution, reopened.reports,
                reopened.reopened_from_tombstone) == ("pending", None, 3, True)
        [signal] = [event for event in journal.read()
                    if event.body.get("kind") == "tombstone_auto_reopened"]
        assert signal.key == f"tombstone-reopen/{first.id}/3"
        assert signal.body == {"kind": "tombstone_auto_reopened", "box_id": first.id,
                               "signature": reopened.signature, "reports": 3}


def test_rereport_callback_failure_retries_the_stable_threshold_key(tmp_path):
    state = tmp_path / "state"
    with Journal(state, clock=lambda: T0) as journal:
        callback = journal_rereport_callback(journal)
        attempts = 0

        def fail_once(message):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("journal unavailable")
            callback(message)

        queue = Box(state, fs=LocalFilesystem(), clock=lambda: T0,
                    rereport_callback=fail_once)
        first = queue.enqueue(message_class="suggestion", summary="one", detail="same 1",
                              origin="host")
        queue.resolve(first.id, status="tombstoned", link="existing", note="duplicate")
        queue.enqueue(message_class="suggestion", summary="two", detail="same 2",
                      origin="host")

        with pytest.raises(RuntimeError, match="journal unavailable"):
            queue.enqueue(message_class="suggestion", summary="three", detail="same 3",
                          origin="host")
        failed = queue.get(first.id)
        assert (failed.status, failed.reports) == ("tombstoned", 2)
        assert not [event for event in journal.read()
                    if event.body.get("kind") == "tombstone_auto_reopened"]

        queue.enqueue(message_class="suggestion", summary="three", detail="same 3",
                      origin="host")
        reopened = queue.get(first.id)
        [signal] = [event for event in journal.read()
                    if event.body.get("kind") == "tombstone_auto_reopened"]
        assert signal.key == f"tombstone-reopen/{first.id}/3"
        assert (reopened.status, reopened.reports) == ("pending", 3)


def test_a_reopened_record_re_tombstoned_at_lifetime_k_does_not_reopen_next_report(tmp_path):
    state = tmp_path / "state"
    with Journal(state, clock=lambda: T0) as journal:
        queue = Box(state, fs=LocalFilesystem(), clock=lambda: T0,
                    rereport_callback=journal_rereport_callback(journal))
        first = queue.enqueue(message_class="suggestion", summary="one", detail="same 1",
                              origin="host")
        queue.resolve(first.id, status="tombstoned", link="existing", note="duplicate")
        queue.enqueue(message_class="suggestion", summary="two", detail="same 2",
                      origin="host")
        queue.enqueue(message_class="suggestion", summary="three", detail="same 3",
                      origin="host")
        queue.resolve(first.id, status="tombstoned", link="existing-again", note="duplicate")

        queue.enqueue(message_class="suggestion", summary="four", detail="same 4",
                      origin="host")

        message = queue.get(first.id)
        assert (message.status, message.reports) == ("tombstoned", 4)
        assert len([event for event in journal.read()
                    if event.body.get("kind") == "tombstone_auto_reopened"]) == 1


def test_no_callback_counts_rereport_but_keeps_threshold_tombstone(tmp_path):
    queue = Box(tmp_path / "state", fs=LocalFilesystem(), clock=lambda: T0)
    first = queue.enqueue(message_class="suggestion", summary="one", detail="same 1",
                          origin="host")
    queue.resolve(first.id, status="tombstoned", link="existing", note="duplicate")
    queue.enqueue(message_class="suggestion", summary="two", detail="same 2", origin="host")
    with pytest.raises(RereportCallbackRequired, match=REREPORT_PAVED_ROAD):
        queue.enqueue(message_class="suggestion", summary="three", detail="same 3",
                      origin="host")
    message = queue.get(first.id)
    assert message.reports == 3 and message.status == "tombstoned"
    assert message.resolution is not None and not message.reopened_from_tombstone
    assert RereportCallbackRequired.paved_road == REREPORT_PAVED_ROAD
    with pytest.raises(RereportCallbackRequired, match=REREPORT_PAVED_ROAD):
        queue.enqueue(message_class="suggestion", summary="four", detail="same 4",
                      origin="host")
    assert queue.get(first.id).reports == 3


def test_semantic_tombstone_match_uses_record_rereport(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    queue = Box(tmp_path / "state", fs=LocalFilesystem(), clock=lambda: T0)
    original = queue.enqueue(message_class="suggestion", summary="old", detail="old",
                             origin="old")
    queue.resolve(original.id, status="tombstoned", link="existing", note="old")
    incoming = queue.enqueue(message_class="suggestion", summary="new", detail="new",
                             origin="new")
    record = Record(id="tombstone-000001", kind="tombstone", link="existing",
                    reopen_after_days=30, message=original.id, body="same concern")
    write(repo, record, fs=LocalFilesystem())
    calls = []
    shared = queue.record_rereport
    shared_resolve = queue.resolve

    def counted(message_id, **kwargs):
        calls.append(("rereport", message_id, kwargs))
        return shared(message_id, **kwargs)

    def resolved(message_id, **kwargs):
        calls.append(("resolve", message_id))
        return shared_resolve(message_id, **kwargs)

    queue.record_rereport = counted
    queue.resolve = resolved
    consumer = SimpleNamespace(_repo=repo, _box=queue, _report=lambda _line: None)
    verdict = TriageTombstone(
        verdict="tombstone", link=record.id, reopen_after_days=30,
        rationale="same concern", produced_by_spec_version="1.0", produced_at_sha="abc")
    asyncio.run(Triage._apply(consumer, queue.get(incoming.id), verdict))
    assert calls == [("rereport", original.id, {"incoming_id": incoming.id}),
                     ("resolve", incoming.id)]
    assert queue.get(original.id).reports == 2
    assert queue.get(incoming.id).resolution.link == record.id
    with pytest.raises(ValueError, match="not pending"):
        asyncio.run(Triage._apply(consumer, queue.get(incoming.id), verdict))
    assert calls[-1] == ("resolve", incoming.id)
    assert queue.get(original.id).reports == 2


@pytest.mark.parametrize("reports", [3, 4, 7])
def test_first_tombstone_above_threshold_counts_arrival_before_reopen(tmp_path, reports):
    state = tmp_path / "state"
    with Journal(state, clock=lambda: T0) as journal:
        occurrences = []
        queue = Box(state, fs=LocalFilesystem(), clock=lambda: T0,
                    rereport_callback=journal_rereport_callback(journal),
                    occurrence_recorder=lambda **kw: occurrences.append(kw))
        first = queue.enqueue(message_class="suggestion", summary="old", detail="old",
                              origin="host")
        for _ in range(reports - 1):
            queue.record_rereport(first.id)
        queue.resolve(first.id, status="tombstoned", link="existing", note="duplicate")
        updated = queue.record_rereport(first.id)
        assert (updated.status, updated.reports) == ("pending", reports + 1)
        [signal] = journal.read()
        assert signal.type == "signal"
        assert signal.key == f"tombstone-reopen/{first.id}/{reports + 1}"
        assert signal.body == {"kind": "tombstone_auto_reopened", "box_id": first.id,
                               "signature": updated.signature, "reports": reports + 1}
        assert occurrences[-1]["occurrence_id"] == f"{first.id}/{reports + 1}"


@pytest.mark.parametrize("incoming_id", [None, "box-000002-feedface"])
def test_callback_free_refusal_has_explicit_marker_and_retries_at_same_count(
        tmp_path, incoming_id):
    state = tmp_path / "state"
    queue = Box(state, fs=LocalFilesystem(), clock=lambda: T0)
    first = queue.enqueue(message_class="suggestion", summary="old", detail="old",
                          origin="host")
    queue.resolve(first.id, status="tombstoned", link="existing", note="duplicate")
    queue.record_rereport(first.id)
    with pytest.raises(RereportCallbackRequired):
        queue.record_rereport(first.id)
    assert queue.get(first.id).pending_threshold_reopen
    with Journal(state, clock=lambda: T0) as journal:
        backed = Box(state, fs=LocalFilesystem(), clock=lambda: T0,
                     rereport_callback=journal_rereport_callback(journal))
        updated = backed.record_rereport(first.id, incoming_id=incoming_id)
        assert (updated.status, updated.reports) == ("pending", 3 if incoming_id is None else 4)
        assert not updated.pending_threshold_reopen
        [signal] = journal.read()
        assert signal.key == f"tombstone-reopen/{first.id}/3"
        assert signal.body["reports"] == 3
        if incoming_id is not None:
            assert backed.record_rereport(first.id, incoming_id=incoming_id).reports == 4


def test_standalone_ingest_counts_and_refuses_threshold_reopen(tmp_path):
    queue = Box(tmp_path / "state", fs=LocalFilesystem(), clock=lambda: T0)
    source = tmp_path / "ideas.md"
    source.write_text("same concern\n")
    ingest(queue, source)
    [message] = queue.pending()
    tombstone = queue.resolve(message.id, status="tombstoned", link="existing",
                              note="duplicate")
    ingest(queue, source)
    with pytest.raises(RereportCallbackRequired, match=REREPORT_PAVED_ROAD):
        ingest(queue, source)
    updated = queue.get(message.id)
    assert (updated.status, updated.reports) == ("tombstoned", 3)
    assert updated.resolution == tombstone.resolution
    assert updated.pending_threshold_reopen and not updated.reopened_from_tombstone


@pytest.mark.parametrize("failure", ["callback", "after_journal", "resolve"])
def test_semantic_match_retries_without_losing_or_double_counting_arrival(
        tmp_path, failure):
    state = tmp_path / "state"
    repo = tmp_path / "repo"
    repo.mkdir()
    with Journal(state, clock=lambda: T0) as journal:
        callback = journal_rereport_callback(journal)
        failed = False

        def fail_once(message):
            nonlocal failed
            if not failed and failure != "resolve":
                failed = True
                if failure == "after_journal":
                    callback(message)
                raise RuntimeError("journal interrupted")
            callback(message)

        queue = Box(state, fs=LocalFilesystem(), clock=lambda: T0,
                    rereport_callback=fail_once)
        original = queue.enqueue(message_class="suggestion", summary="old", detail="old",
                                 origin="old")
        queue.resolve(original.id, status="tombstoned", link="existing", note="old")
        queue.record_rereport(original.id)
        incoming = queue.enqueue(message_class="suggestion", summary="new", detail="new",
                                 origin="new")
        record = Record(id="tombstone-000001", kind="tombstone", link="existing",
                        reopen_after_days=30, message=original.id, body="same concern")
        write(repo, record, fs=LocalFilesystem())
        resolve = queue.resolve

        def fail_resolution_once(message_id, **kwargs):
            nonlocal failed
            if not failed:
                failed = True
                raise RuntimeError("resolution interrupted")
            return resolve(message_id, **kwargs)

        if failure == "resolve":
            queue.resolve = fail_resolution_once
        consumer = SimpleNamespace(_repo=repo, _box=queue, _report=lambda _line: None)
        verdict = TriageTombstone(
            verdict="tombstone", link=record.id, reopen_after_days=30,
            rationale="same concern", produced_by_spec_version="1.0", produced_at_sha="abc")
        with pytest.raises(RuntimeError, match="interrupted"):
            asyncio.run(Triage._apply(consumer, queue.get(incoming.id), verdict))
        assert queue.get(incoming.id).status == "pending"
        assert queue.get(original.id).reports == (3 if failure == "resolve" else 2)

        asyncio.run(Triage._apply(consumer, queue.get(incoming.id), verdict))
        updated = queue.get(original.id)
        assert (updated.status, updated.reports) == ("pending", 3)
        assert updated.rereport_ids == (incoming.id,)
        assert queue.get(incoming.id).status == "tombstoned"
        [signal] = journal.read()
        assert signal.key == f"tombstone-reopen/{original.id}/3"
        assert signal.body["reports"] == 3


@pytest.mark.parametrize("reopened", [False, True])
def test_reopened_retro_author_is_draft_then_clears_marker_and_bridges(
        checkout, monkeypatch, reopened):
    from squatch.baseline import BaselineResolution
    monkeypatch.setattr("squatch.author.resolve_baseline",
                        lambda config, events, *, specs_dir: BaselineResolution("GO", True))
    config = (checkout / "config.yaml").read_text() + (
        "engine_plane_safety_inventory: [specs/]\n"
        "box_policy: {retro_finding: confirmed}\n")
    values = _retro_values()
    box, message_id, _reports, go = setup_author(
        checkout, FakeLLM(reply(ticket()), review_reply("approve")),
        message_class="retro_finding", enqueue_kwargs=values, config_text=config)
    path, message = next((path, item) for path, item in box._records()
                         if item.id == message_id)
    box._replace(path, message.model_copy(update={"reopened_from_tombstone": reopened}))

    assert asyncio.run(go()) == "parser-ticket"
    authored = (checkout / "tickets/parser-ticket/ticket.md").read_text()
    assert f"state: {'draft' if reopened else 'confirmed'}" in authored
    assert not box.get(message_id).reopened_from_tombstone
    [bridge] = [event for event in read_events(checkout / STATE)
                if event.body.get("kind") == "retro_ticket_authored"]
    assert bridge.key == "retro-ticket/parser-ticket"
    assert bridge.body == {"kind": "retro_ticket_authored", "box_id": message_id,
                           "retro_report_key": "retro/000001",
                           "ticket_stem": "parser-ticket"}
    events = list(read_events(checkout / STATE))
    intake = next(event for event in events if event.body.get("kind") == "ticket_intake")
    assert events.index(bridge) < events.index(intake)


def test_retro_bridge_failure_precedes_commit_and_discards_ticket(checkout, monkeypatch):
    def fail_bridge(self, message, stem):
        raise RuntimeError("journal unavailable")

    monkeypatch.setattr("squatch.author.Author._record_retro_bridge", fail_bridge)
    box, message_id, reports, go = setup_author(
        checkout, FakeLLM(reply(ticket()), review_reply("approve")),
        message_class="retro_finding", enqueue_kwargs=_retro_values())
    path, message = next((path, item) for path, item in box._records()
                         if item.id == message_id)
    box._replace(path, message.model_copy(update={"reopened_from_tombstone": True}))

    assert asyncio.run(go()) is None
    assert not (checkout / "tickets/parser-ticket").exists()
    assert box.get(message_id).status == "pending"
    assert box.get(message_id).reopened_from_tombstone
    assert any("journal unavailable" in line and "left pending" in line for line in reports)
    assert not [event for event in read_events(checkout / STATE)
                if event.body.get("kind") in ("ticket_intake", "retro_ticket_authored")]


class _MemoryJournal:
    def __init__(self):
        self.events = []

    def read(self):
        return iter(self.events)

    def append(self, event_type, body, *, ticket=None, key=None):
        persisted = json.loads(json.dumps(body))
        event = Event(1, event_type, datetime.now(timezone.utc).isoformat(), ticket, key,
                      persisted)
        self.events.append(event)
        return event


def test_merge_uses_only_unique_journal_bridge_and_exact_success_predicate():
    journal = _MemoryJournal()
    merge = object.__new__(Merge)
    merge._journal = journal
    merge._box = SimpleNamespace(
        by_origin=lambda *_args: (_ for _ in ()).throw(AssertionError("Box lookup")))
    retro_ticket = SimpleNamespace(stem="retro-fix", source="box:retro_finding")
    other_source = SimpleNamespace(stem="retro-fix", source="human")

    assert merge._retro_provenance_findings(other_source, ("specs/review.md",)) == []
    assert merge._retro_provenance_findings(retro_ticket, ("squatch/box.py",)) == []
    [missing] = merge._retro_provenance_findings(retro_ticket, ("specs/review.md",))
    assert missing.code == "retro_provenance" and "missing" in missing.message

    bridge_body = {"kind": "retro_ticket_authored", "box_id": "box-000001-deadbeef",
                   "retro_report_key": "retro/000001", "ticket_stem": "retro-fix"}
    journal.append("signal", bridge_body, key="retro-ticket/retro-fix")
    assert merge._retro_provenance_findings(retro_ticket, ("specs/review.md",)) == []
    merge._record_retro_merge(
        retro_ticket, "abc123", ("specs/z.md", "src/x.py", "specs/a.md"))
    merge._record_retro_merge(
        retro_ticket, "abc123", ("specs/z.md", "src/x.py", "specs/a.md"))
    [signal] = [event for event in journal.events
                if event.body.get("kind") == "retro_prompt_spec_change_merged"]
    assert signal.key == "retro-prompt-spec-change/retro-fix/abc123"
    assert signal.body == {
        "kind": "retro_prompt_spec_change_merged", "box_id": "box-000001-deadbeef",
        "retro_report_key": "retro/000001", "ticket_stem": "retro-fix",
        "squash_sha": "abc123", "changed_spec_paths": ["specs/a.md", "specs/z.md"]}

    journal.append("signal", {**bridge_body, "box_id": "box-000002-feedface"},
                   key="retro-ticket/retro-fix-duplicate")
    [ambiguous] = merge._retro_provenance_findings(retro_ticket, ("specs/review.md",))
    assert ambiguous.code == "retro_provenance" and "ambiguous" in ambiguous.message


@pytest.mark.parametrize(("path", "expected"), [
    ("squatch/merge.py", 1),
    ("squatch/author.py", 1),
    ("squatch/triage.py", 1),
    ("squatch/stages.py", 1),
    ("squatch/runner.py", 2),
    ("squatch/daemon.py", 1),
    ("squatch/drain.py", 0),
    ("squatch/serve.py", 0),
    ("squatch/__main__.py", 1),
])
def test_every_production_box_constructor_with_journal_access_binds_callback(path, expected):
    source = (Path(__file__).resolve().parent.parent / path).read_text()
    calls = [node for node in ast.walk(ast.parse(source))
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
             and node.func.id == "Box"]
    assert len(calls) == expected
    assert all(any(keyword.arg == "rereport_callback" for keyword in call.keywords)
               for call in calls)


def test_non_writer_box_constructors_remain_the_two_explicit_exceptions():
    root = Path(__file__).resolve().parent.parent
    counts = {}
    for path in ("squatch/box.py", "squatch/status.py"):
        calls = [node for node in ast.walk(ast.parse((root / path).read_text()))
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                 and node.func.id == "Box"]
        counts[path] = len(calls)
        assert len(calls) == 1
        assert all(keyword.arg != "rereport_callback"
                   for call in calls for keyword in call.keywords)
    assert set(counts) == {"squatch/box.py", "squatch/status.py"}


async def test_merge_base_failure_route_uses_verification_box_without_provenance_lookup(
        repo, env):
    agent = MergeAgent(
        merge_answer("implemented"), merge_review("approve"),
        actions=[merge_implementer(env, WIDGET)])
    harness = MergeHarness(repo, env, agent)
    delivery = await merge_deliver(harness, verify=BASE_RED)
    merge = merge_of(harness)
    merge._box.by_origin = lambda *_args: (_ for _ in ()).throw(
        AssertionError("Merge must not read retro provenance from Box"))

    admission = await merge.admit(ticket_of(harness), delivery, run_seq=0)

    assert admission.outcome == "ok" and admission.findings == []
    [report] = list((harness.state / "box").glob("*.json"))
    message = json.loads(report.read_text())
    assert message["outcome"] == "base_red" and message["reports"] == 2


@pytest.mark.parametrize("daemon", [False, True])
@pytest.mark.parametrize("case", ["valid", "missing", "ambiguous", "source", "path"])
async def test_retro_signal_at_real_successful_admission(repo, env, daemon, case):
    source = "human" if case == "source" else "box:retro_finding"
    path = "specs/proposal.txt" if case == "path" else "specs/proposal.md"
    text = TICKET.format(verify=GREEN, frontmatter=f"source: {source}\nstate: confirmed")
    text = text.replace("- squatch/widget.py", "- squatch/widget.py\n- specs/")
    agent = MergeAgent(merge_answer("implemented"), merge_review("approve"),
                       actions=[merge_implementer(env, WIDGET, (path, "New instructions.\n"))])
    harness = MergeHarness(repo, env, agent)
    ticket_path = repo / "tickets" / STEM / "ticket.md"
    ticket_path.parent.mkdir(parents=True)
    ticket_path.write_text(text)
    await Intake(repo=repo, git=harness.git, journal=harness.journal,
                 fs=LocalFilesystem()).commit(STEM, source=source, state="confirmed")
    delivery = await merge_deliver(harness, text=text)
    retro_ticket = ticket_of(harness)
    if case in ("valid", "ambiguous"):
        harness.journal.append("signal", {
            "kind": "retro_ticket_authored", "box_id": "box-000001-deadbeef",
            "retro_report_key": "retro/000001", "ticket_stem": STEM,
        }, key=f"retro-ticket/{STEM}")
    if case == "ambiguous":
        harness.journal.append("signal", {
            "kind": "retro_ticket_authored", "box_id": "box-000002-feedface",
            "retro_report_key": "retro/000002", "ticket_stem": STEM,
        }, key=f"retro-ticket/{STEM}-duplicate")
    pipeline = composed_pipeline_of(harness)
    pipeline.stages = SettledStages(delivery)
    pipeline.merge._box = SimpleNamespace()
    if daemon:
        pipeline.select_daemon_admission()
    before = await harness.git.rev_parse(repo, "main")

    result = await pipeline.run(retro_ticket, run_seq=0)

    events = list(harness.journal.read())
    signals = [event for event in events
               if event.body.get("kind") == "retro_prompt_spec_change_merged"]
    terminals = [event for event in events if event.type == "state_transition"
                 and event.body.get("to") == "merged"]
    if case in ("missing", "ambiguous"):
        assert result.outcome == "gate_failed"
        assert any(finding.code == "retro_provenance" for finding in result.findings)
        assert await harness.git.rev_parse(repo, "main") == before
        assert not signals and not terminals
        assert harness.worktree().exists()
        return
    assert result.outcome == "ok", result.findings
    [terminal] = terminals
    sha = await harness.git.rev_parse(repo, "main")
    assert sha != before and terminal.body["commit"] == sha
    if case != "valid":
        assert signals == []
        return
    [signal] = signals
    assert signal.type == "signal"
    assert signal.key == f"retro-prompt-spec-change/{STEM}/{sha}"
    assert signal.body == {
        "kind": "retro_prompt_spec_change_merged", "box_id": "box-000001-deadbeef",
        "retro_report_key": "retro/000001", "ticket_stem": STEM,
        "squash_sha": sha, "changed_spec_paths": [path],
    }
    assert events.index(signal) < events.index(terminal)
    pipeline.merge._record_retro_merge(retro_ticket, sha, (path, WIDGET[0]))
    assert list(harness.journal.read()) == events
