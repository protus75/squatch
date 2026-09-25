import asyncio
import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from test_cli import GOOD, STATE, T0, checkout, git_env

from squatch.author import (AUTHOR_STUCK_SECONDS, AuthoredTicket, Author, AuthorInput,
                            author_stage)
from squatch.box import Box
from squatch.config import load
from squatch.enginelog import EngineLog
from squatch.git import Git
from squatch.journal import Journal, read_events
from squatch.llm import FakeLLM, Hang
from squatch.redact import Redactor
from squatch.seams import LocalFilesystem, SubprocessExec
from squatch.specs import DATA_MARKER, load_spec
from squatch.tickets import TicketSchemaGate, stamp
from squatch.triage import Triage, TriageAuthor

ROOT = Path(__file__).resolve().parent.parent


def verdict(**over):
    return TriageAuthor(
        produced_by_spec_version="1.0", produced_at_sha="abc", verdict="author",
        summary="write parser", kind="feature", priority="P2",
        goal="The parser lands.", why="It is needed.", **over)


def ticket(*, bypass=False):
    text = GOOD.format(depends="none")
    if bypass:
        text = text.replace(
            "kind: feature\n", "kind: feature\ngate_bypass:\n"
            "  - {code: diff_budget, reason: generated output}\n")
    return text


def reply(text, stem="parser-ticket"):
    return json.dumps({"stem": stem, "ticket": text})


def setup_author(repo, llm, *, message_class="suggestion", config_text=None,
                 bug_origin=None, has_repro=None, message_update=None):
    if config_text is not None:
        (repo / "config.yaml").write_text(config_text)
    config = load(None, cwd=repo)
    fs = LocalFilesystem()
    redact = Redactor.from_config(config, {})
    box = Box(repo / STATE, fs=fs, clock=lambda: T0)
    message_id = box.enqueue(message_class=message_class, summary="request parser",
                             detail="raw details", origin="test", bug_origin=bug_origin,
                             has_repro=has_repro).id
    box.record_triage(message_id, verdict().model_dump(mode="json"))
    reports = []

    async def go():
        git = Git(SubprocessExec(), env=git_env(repo.parent), timeout=60)
        sha = await git.rev_parse(repo, "HEAD")
        with Journal(repo / STATE, clock=lambda: T0) as journal:
            author = Author(
                repo=repo, config=config, git=git, fs=fs, clock=lambda: T0,
                journal=journal, llm=llm,
                log=EngineLog(repo / STATE, clock=lambda: T0, redact=redact),
                redact=redact, report=reports.append)
            message = box.get(message_id)
            if message_update:
                message = message.model_copy(update=message_update)
            result = await author.run(load_spec(ROOT / "specs" / "author.md"), message, verdict(),
                                      pass_number=0, sha=sha)
        return result

    return box, message_id, reports, go


def test_spec_stage_and_render_contract():
    spec = load_spec(ROOT / "specs" / "author.md")
    assert (spec.surface, spec.consumes, spec.emits, spec.gates) == (
        "author", "AuthorInput", "AuthoredTicket", ("ticket_schema",))
    assert spec.slots == (
        "message", "triage", "ticket_contract", "plane", "tree", "context_files")
    assert spec.optional == {"context_files"}
    stage = author_stage(spec)
    assert (stage.name, stage.surface, stage.consumes, stage.emits) == (
        "author", "author", AuthorInput, AuthoredTicket)
    assert [gate.code for gate in stage.gates] == ["ticket_schema"]
    rendered = stage.render(AuthorInput(
        produced_by_spec_version="x", produced_at_sha="abc",
        message_id="box-000001-deadbeef", message_class="suggestion",
        summary="summary", detail="detail", origin="test", triage=verdict(),
        ticket_contract="## 13. Ticket contract\ncontract", plane="(none)",
        tree="squatch/x.py"), ())
    assert f'{DATA_MARKER}data name="message" origin="untrusted"' in rendered
    assert f'{DATA_MARKER}data name="ticket_contract" origin="engine"' in rendered


def test_authored_ticket_stem_and_schema_gate(checkout):
    common = {"produced_by_spec_version": "1.0", "produced_at_sha": "abc"}
    with pytest.raises(ValidationError, match="stem"):
        AuthoredTicket(**common, stem="Bad_Stem", ticket=ticket())

    async def check(stem, text):
        artifact = AuthoredTicket(**common, stem=stem, ticket=text)
        return await TicketSchemaGate().check(artifact, checkout)

    missing = asyncio.run(check("missing-verification",
                                ticket().replace("## Verification", "## Not verification")))
    assert missing.verdict == "fail" and all(f.paved_road for f in missing.findings)
    existing = checkout / "tickets" / "existing" / "ticket.md"
    existing.parent.mkdir(parents=True)
    existing.write_text(ticket())
    collision = asyncio.run(check("existing", ticket()))
    assert any("already exists" in f.message for f in collision.findings)
    bad_context = asyncio.run(check(
        "bad-context", ticket().replace("- squatch/existing.py", "- squatch/missing.py")))
    assert any("does not exist" in f.message for f in bad_context.findings)
    assert all(f.paved_road for report in (missing, collision, bad_context)
               for f in report.findings)


def test_author_reprompts_then_commits_and_resolves(checkout):
    invalid = ticket().replace("## Time budget\n- expected: 20m\n- stuck: 40m\n", "")
    llm = FakeLLM(reply(invalid), reply(ticket()))
    box, message_id, reports, go = setup_author(checkout, llm)

    assert asyncio.run(go()) == "parser-ticket"

    assert len(llm.requests) == 2
    assert "ticket_schema" in llm.requests[1].rendered and "Time budget" in llm.requests[1].rendered
    events = tuple(read_events(checkout / STATE))
    assert [e.key for e in events if e.type == "effect_completion"] == [
        "llm/author/0/author/1/1", "llm/author/0/author/1/2"]
    [intake] = [e for e in events if e.type == "signal"
                and e.body.get("kind") == "ticket_intake"]
    assert intake.ticket == "parser-ticket" and intake.body["source"] == "box:suggestion"
    committed = (checkout / "tickets/parser-ticket/ticket.md").read_text()
    assert "source: box:suggestion" in committed and "state: draft" in committed
    message = box.get(message_id)
    assert message.status == "authored" and message.resolution.link == "parser-ticket"
    assert any("authored as parser-ticket" in line for line in reports)


def test_retry_allowance_exhaustion_leaves_recorded_verdict_pending(checkout):
    config = (checkout / "config.yaml").read_text() + "caps: {retry: 1, diagnosis: 1}\n"
    invalid = ticket().replace("## Time budget\n- expected: 20m\n- stuck: 40m\n", "")
    box, message_id, reports, go = setup_author(
        checkout, FakeLLM(reply(invalid), reply(invalid)), config_text=config)

    assert asyncio.run(go()) is None
    message = box.get(message_id)
    assert message.status == "pending" and message.triage["verdict"] == "author"
    assert not (checkout / "tickets/parser-ticket").exists()
    assert any("retry allowance of 1 spent" in line for line in reports)


def test_hung_author_is_aborted_and_left_pending(checkout, monkeypatch):
    import squatch.author as module

    monkeypatch.setattr(module, "AUTHOR_STUCK_SECONDS", 0.001)
    llm = FakeLLM(Hang(resist=True))
    box, message_id, _, go = setup_author(checkout, llm)

    assert asyncio.run(go()) is None
    assert llm.aborted == 1 and box.get(message_id).status == "pending"


def test_gate_bypass_forces_draft_under_binding_go(checkout, monkeypatch):
    monkeypatch.setattr("squatch.author.go_binds", lambda config, events: True)
    config = (checkout / "config.yaml").read_text() + (
        "engine_plane_safety_inventory: [specs/]\n"
        "box_policy: {failure_report: confirmed}\n")
    box, message_id, _, go = setup_author(
        checkout, FakeLLM(reply(ticket(bypass=True))),
        message_class="failure_report", config_text=config)

    assert asyncio.run(go()) == "parser-ticket"
    text = (checkout / "tickets/parser-ticket/ticket.md").read_text()
    assert "state: draft" in text
    assert box.get(message_id).status == "authored"


def test_commit_failure_discards_ticket_and_leaves_message_pending(checkout, monkeypatch):
    async def fail_commit(self, stem, **stamps):
        await self._git.add(self._repo, [self._rel(stem)])
        raise RuntimeError("commit lane unavailable")

    monkeypatch.setattr("squatch.author.Intake.commit", fail_commit)
    box, message_id, reports, go = setup_author(
        checkout, FakeLLM(reply(ticket())))

    assert asyncio.run(go()) is None
    assert not (checkout / "tickets/parser-ticket").exists()
    message = box.get(message_id)
    assert message.status == "pending" and message.triage["verdict"] == "author"
    assert any("commit lane unavailable" in line and "left pending" in line
               for line in reports)


@pytest.mark.parametrize("message_update, field", [
    ({"bug_origin": None}, "bug_origin"),
    ({"bug_origin": "robot"}, "bug_origin"),
    ({"has_repro": None}, "has_repro"),
    ({"has_repro": 1}, "has_repro"),
])
def test_invalid_bug_policy_input_is_a_per_item_failure_before_write(
        checkout, message_update, field):
    llm = FakeLLM(reply(ticket()))
    box, message_id, reports, go = setup_author(
        checkout, llm, message_class="bug_report", bug_origin="player", has_repro=True,
        message_update=message_update)

    assert asyncio.run(go()) is None
    assert llm.requests == []
    assert not (checkout / "tickets/parser-ticket").exists()
    message = box.get(message_id)
    assert message.status == "pending" and message.triage["verdict"] == "author"
    assert any(field in line and "left pending" in line for line in reports)


def test_invalid_bug_policy_item_does_not_stop_later_authoring(
        checkout, monkeypatch):
    config = load(None, cwd=checkout)
    fs = LocalFilesystem()
    redact = Redactor.from_config(config, {})
    box = Box(checkout / STATE, fs=fs, clock=lambda: T0)
    bad_id = box.enqueue(
        message_class="bug_report", summary="bad", detail="bad detail", origin="test-bad",
        bug_origin="player", has_repro=True).id
    good_id = box.enqueue(
        message_class="suggestion", summary="good", detail="good detail",
        origin="test-good").id
    for message_id in (bad_id, good_id):
        box.record_triage(message_id, verdict().model_dump(mode="json"))
    pending = [
        box.get(bad_id).model_copy(update={"bug_origin": "robot"}),
        box.get(good_id),
    ]
    monkeypatch.setattr("squatch.triage.Box.pending", lambda self: pending)
    llm = FakeLLM(reply(ticket(), stem="later-ticket"))
    reports = []

    async def go():
        git = Git(SubprocessExec(), env=git_env(checkout.parent), timeout=60)
        with Journal(checkout / STATE, clock=lambda: T0) as journal:
            consumer = Triage(
                repo=checkout, config=config, git=git, fs=fs, clock=lambda: T0,
                journal=journal, llm=llm,
                log=EngineLog(checkout / STATE, clock=lambda: T0, redact=redact),
                redact=redact, report=reports.append)
            await consumer.run(load_spec(ROOT / "specs" / "triage.md"))

    asyncio.run(go())

    first = box.get(bad_id)
    assert first.status == "pending" and first.triage["verdict"] == "author"
    assert box.get(good_id).status == "authored"
    assert (checkout / "tickets/later-ticket/ticket.md").is_file()
    assert len(llm.requests) == 1
    [passed] = [event for event in read_events(checkout / STATE)
                if event.type == "signal" and event.body.get("kind") == "triage_pass"]
    assert passed.body["skipped"] == [bad_id]
    assert passed.body["triaged"]["authored"] == ["later-ticket"]


def test_stuck_constant_is_the_shipped_budget():
    assert AUTHOR_STUCK_SECONDS == 900
