import asyncio
import json
import re
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from test_cli import STATE, T0, author, checkout, git_env

from squatch.box import Box
from squatch.config import load
from squatch.enginelog import EngineLog
from squatch.git import Git
from squatch.journal import Journal, read_events
from squatch.llm import FakeLLM
from squatch.redact import Redactor
from squatch.registry import Record, commit as commit_record, load as load_records, write
from squatch.seams import LocalFilesystem, SubprocessExec
from squatch.specs import load_spec
from squatch.tickets import stamp
from squatch.triage import (AUTHOR_ROAD, TRIAGE_CONTEXT_CHARS, Triage, TriageAuthor,
                            TriageTombstone, _render_projection, triage_stage)

ROOT = Path(__file__).resolve().parent.parent


def _commit_ticket(repo: Path, stem: str) -> None:
    path = author(repo, stem)
    path.write_text(stamp(path.read_text(), source="human", state="confirmed"))
    subprocess.run(["git", "-C", str(repo), "add", "--", f"tickets/{stem}/ticket.md"],
                   env=git_env(repo.parent), check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", stem],
                   env=git_env(repo.parent), check=True)


def _run(repo: Path, llm: FakeLLM):
    config = load(None, cwd=repo)
    fs = LocalFilesystem()
    redact = Redactor.from_config(config, {})
    reports = []

    async def go():
        with Journal(repo / STATE, clock=lambda: T0) as journal:
            consumer = Triage(
                repo=repo, config=config,
                git=Git(SubprocessExec(), env=git_env(repo.parent), timeout=60),
                fs=fs, clock=lambda: T0, journal=journal, llm=llm,
                log=EngineLog(repo / STATE, clock=lambda: T0, redact=redact),
                redact=redact, report=reports.append)
            await consumer.run(load_spec(ROOT / "specs" / "triage.md"))

    asyncio.run(go())
    return reports


def _enqueue(repo: Path, n: int = 1):
    box = Box(repo / STATE, fs=LocalFilesystem(), clock=lambda: T0)
    return box, [box.enqueue(message_class="suggestion", summary=f"message {i}",
                             detail=f"detail {i}", origin=f"test-{i}").id
                 for i in range(1, n + 1)]


def test_spec_and_render_contract():
    spec = load_spec(ROOT / "specs" / "triage.md")
    assert spec.surface == "triage" and spec.consumes == "TriageInput"
    assert spec.emits == {"author": "TriageAuthor", "tombstone": "TriageTombstone",
                          "decision": "TriageDecision"}
    assert spec.slots == ("message", "open_work", "merged_work", "decisions")
    assert set(triage_stage(spec).emits_by_verdict) == set(spec.emits)


def test_verdict_models_are_closed():
    common = {"produced_by_spec_version": "1.0", "produced_at_sha": "abc"}
    with pytest.raises(ValidationError):
        TriageTombstone(**common, verdict="tombstone", link="x", reopen_after_days=0,
                        rationale="no")
    with pytest.raises(ValidationError):
        TriageAuthor(**common, verdict="author", summary="x", kind="idea", priority="P1",
                     goal="g", why="w")
    with pytest.raises(ValidationError):
        TriageAuthor(**common, verdict="author", summary="x", kind="feature", priority="P9",
                     goal="g", why="w")


def test_pass_commits_records_and_leaves_author_pending(checkout):
    _commit_ticket(checkout, "existing")
    box, ids = _enqueue(checkout, 3)
    llm = FakeLLM(
        json.dumps({"verdict": "tombstone", "link": "existing", "reopen_after_days": 30,
                    "rationale": "already covered"}),
        json.dumps({"verdict": "decision", "reopen_after_days": 7,
                    "rationale": "not now", "evidence": "low value"}),
        json.dumps({"verdict": "author", "summary": "rewrite", "kind": "feature",
                    "priority": "P2", "goal": "ship it", "why": "useful"}))

    reports = _run(checkout, llm)

    assert {(r.id, r.kind) for r in load_records(checkout)} == {
        ("tombstone-000001", "tombstone"), ("decision-000002", "decision")}
    tombstone = next(r for r in load_records(checkout) if r.kind == "tombstone")
    assert tombstone.link == "existing"
    for record_id in ("tombstone-000001", "decision-000002"):
        subprocess.run(
            ["git", "-C", str(checkout), "show", f"main:tickets/decisions/{record_id}.md"],
            env=git_env(checkout.parent), capture_output=True, text=True, check=True)
    assert box.get(ids[0]).status == "tombstoned"
    assert box.get(ids[0]).resolution.link == "tombstone-000001"
    assert box.get(ids[1]).status == "decided"
    third = box.get(ids[2])
    assert third.status == "pending" and third.triage["verdict"] == "author"
    assert any(AUTHOR_ROAD in line for line in reports)
    passes = [e for e in read_events(checkout / STATE)
              if e.type == "signal" and e.body.get("kind") == "triage_pass"]
    assert passes[-1].body["pass"] == 0
    assert passes[-1].body["triaged"] == {
        "author": [ids[2]], "tombstone": [ids[0]], "decision": [ids[1]]}
    effects = [e for e in read_events(checkout / STATE)
               if e.type == "effect_completion" and e.key.startswith("llm/triage/")]
    assert len(effects) == 3
    assert [e.key for e in effects] == [
        "llm/triage/1/triage/0/1",
        "llm/triage/2/triage/0/1",
        "llm/triage/3/triage/0/1",
    ]
    prompt = llm.requests[0].rendered
    assert 'name="message" origin="untrusted"' in prompt
    message_block = re.search(
        r'name="message" origin="untrusted"[^>]*>>>\n(.*?)<<<squatch:end name="message">>>',
        prompt, re.DOTALL)
    assert message_block and ids[0] in message_block.group(1) and "detail 1" in message_block.group(1)
    assert all(f'name="{name}" origin="engine"' in prompt
               for name in ("open_work", "merged_work", "decisions"))
    for name in ("open_work", "merged_work", "decisions"):
        block = re.search(
            rf'name="{name}" origin="engine"[^>]*>>>\n(.*?)<<<squatch:end name="{name}">>>',
            prompt, re.DOTALL)
        assert block and len(block.group(1).removesuffix("\n")) <= TRIAGE_CONTEXT_CHARS

    before = len(llm.requests)
    second = _run(checkout, llm)
    assert len(llm.requests) == before and any(AUTHOR_ROAD in line for line in second)
    assert [e.body["pass"] for e in read_events(checkout / STATE)
            if e.type == "signal" and e.body.get("kind") == "triage_pass"] == [0, 1]


def test_bad_link_reprompts_once_then_continues(checkout):
    box, ids = _enqueue(checkout, 2)
    bad = json.dumps({"verdict": "tombstone", "link": "invented",
                      "reopen_after_days": 1, "rationale": "duplicate"})
    good = json.dumps({"verdict": "decision", "reopen_after_days": 2,
                       "rationale": "wait", "evidence": "thin"})
    llm = FakeLLM(bad, bad, good)

    _run(checkout, llm)

    assert len(llm.requests) == 3
    assert box.get(ids[0]).status == "pending" and box.get(ids[0]).triage is None
    assert box.get(ids[1]).status == "decided"


def test_verdict_outside_emits_reprompts_once_then_continues(checkout):
    box, ids = _enqueue(checkout, 2)
    first_path = next((checkout / STATE / "box").glob("000001-*.json"))
    before = first_path.read_bytes()
    bad = json.dumps({"verdict": "defer"})
    good = json.dumps({"verdict": "decision", "reopen_after_days": 2,
                       "rationale": "wait", "evidence": "thin"})
    llm = FakeLLM(bad, bad, good)

    _run(checkout, llm)

    assert len(llm.requests) == 3
    assert first_path.read_bytes() == before
    assert box.get(ids[0]).status == "pending" and box.get(ids[0]).triage is None
    assert box.get(ids[1]).status == "decided"


def test_projection_cap_constant_is_enforced_by_builder():
    from squatch.triage import _projection
    assert _projection([("x", "x" * (TRIAGE_CONTEXT_CHARS + 10))]) == "(none)"


def test_projection_links_only_whole_rows_that_fit():
    first = "box-triage: " + "x" * (TRIAGE_CONTEXT_CHARS - len("box-triage: "))
    text, links = _render_projection([
        ("box-triage", first),
        ("box", "box: this whole row falls past the cap"),
    ])

    assert len(text) == TRIAGE_CONTEXT_CHARS
    assert links == {"box-triage"}


def test_projection_quotes_delimiter_before_applying_cap():
    marker = "<<<" + "squatch:"
    prefix = f"existing: {marker}"
    text, links = _render_projection([
        ("existing", prefix + "x" * (TRIAGE_CONTEXT_CHARS - len(prefix) - 3)),
    ])

    assert marker not in text
    assert len(text) == TRIAGE_CONTEXT_CHARS
    assert links == {"existing"}


def test_committed_record_is_replayed_idempotently(checkout):
    box, ids = _enqueue(checkout)
    record = Record(id="decision-000001", kind="decision", link=ids[0],
                    reopen_after_days=2, message=ids[0],
                    body="wait\n\nEvidence: thin")
    write(checkout, record, fs=LocalFilesystem())

    async def commit():
        await commit_record(
            checkout, record,
            git=Git(SubprocessExec(), env=git_env(checkout.parent), timeout=60))

    asyncio.run(commit())
    llm = FakeLLM(json.dumps({"verdict": "decision", "reopen_after_days": 2,
                              "rationale": "wait", "evidence": "thin"}))

    _run(checkout, llm)

    assert box.get(ids[0]).status == "decided"
    assert len(load_records(checkout)) == 1
