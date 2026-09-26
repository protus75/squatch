"""Direct proofs for the dormant post-admission Rework boundary."""

import ast
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from squatch.config import Config
from squatch.diagnose import DiagnosisRecord
from squatch.driver import Driver, Spool
from squatch.effects import Effects
from squatch.enginelog import EngineLog
from squatch.journal import Journal
from squatch.ladder import Rung, next_rung
from squatch.llm import FakeLLM
from squatch.llmeffect import LLMEffect
from squatch.mergequeue import (Admission, ConflictFacts, MergeQueue,
                                UnresolvedConflictHandoff)
from squatch.providers import Registry
from squatch.redact import Redactor
from squatch.reject import route
from squatch.rework import (SUPERSEDES_SIGNAL, Rework, ReworkOrder,
                            UnresolvedConflictHandoff as ReworkHandoff,
                            rework_stage)
from squatch.seams import LocalFilesystem
from squatch.specs import load_spec
from squatch.tickets import FRONTMATTER_KEYS, lint_ticket, parse_frontmatter

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)
SHA = "abc123"


def ticket(goal="The conflict is resolved.", *, depends="none"):
    return f"""\
---
state: confirmed
source: human
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- {depends}

## Context

## Goal
{goal}

## Why
The unresolved work must return through review.

## Scope in
Resolve the named work.

## Scope out
Do not change unrelated behavior.

## Scope fence
- target.py

## Acceptance criteria
- `target.py` remains observable.

## Verification
```
uv run pytest -q
```

## Definition of rejected
Stop if the ticket cannot be resolved as written.

## Time budget
- expected: 20m
- stuck: 40m
"""


def handoff(run_seq=3):
    return UnresolvedConflictHandoff(
        stem="original-work", branch="original-work", run_seq=run_seq,
        facts=ConflictFacts(stem="original-work", paths=("target.py",), rung="rework"))


def order(**changes):
    body = {"updated_ticket": None, "split_tickets": [], "escalation": None}
    body.update(changes)
    return json.dumps(body)


def prepare_repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "tickets/original-work").mkdir(parents=True)
    (repo / "tickets/original-work/ticket.md").write_text(ticket())
    (repo / "target.py").write_text("VALUE = 1\n")
    return repo


def queue_with(item=None):
    queue = MergeQueue.__new__(MergeQueue)
    queue._slot = asyncio.Lock()
    queue._rework = asyncio.Queue()
    if item is not None:
        queue._rework.put_nowait(item)
    return queue


def driver(tmp_path, journal, llm):
    redactor = Redactor({})
    state = tmp_path / "state"
    effect = LLMEffect(llm=llm, effects=Effects(journal), redact=redactor)
    return Driver(
        llm=effect, spool=Spool(state, fs=LocalFilesystem(), redact=redactor),
        log=EngineLog(state, clock=lambda: NOW, redact=redactor), clock=lambda: NOW)


def run_rework(tmp_path, response, *, queued=None):
    repo = prepare_repo(tmp_path)
    llm = FakeLLM(response)
    journal = Journal(tmp_path / "state", clock=lambda: NOW)
    queue = queue_with(queued or handoff())
    worker = Rework(
        repo=repo, queue=queue, journal=journal, fs=LocalFilesystem(),
        driver=driver(tmp_path, journal, llm),
        spec=load_spec(ROOT / "specs/rework.md"), tier="medium", effort="medium")
    return repo, llm, journal, worker


def lint(repo, stem):
    return lint_ticket(
        (repo / f"tickets/{stem}/ticket.md").read_text(), stem=stem, repo=repo,
        plan=None, resolve_stem=lambda candidate: (
            repo / f"tickets/{candidate}/ticket.md").is_file())


def test_spec_is_one_composite_rework_order_surface():
    spec = load_spec(ROOT / "specs/rework.md")
    assert (spec.surface, spec.consumes, spec.emits, spec.gates) == (
        "rework", "ReworkInput", "ReworkOrder", ("ticket_schema",))
    stage = rework_stage(spec, tier="high", effort="high")
    assert stage.emits is ReworkOrder and stage.surface == "rework"


def test_rework_remains_unreachable_from_the_production_root():
    package = ROOT / "squatch"

    def source(module):
        relative = module.removeprefix("squatch.").replace(".", "/")
        return next((path for path in (
            package / f"{relative}.py", package / relative / "__init__.py")
                     if path.is_file()), None)

    reachable = set()
    pending = ["squatch.__main__"]
    while pending:
        module = pending.pop()
        if module in reachable or (path := source(module)) is None:
            continue
        reachable.add(module)
        imports = set()
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names
                               if alias.name.startswith("squatch."))
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module == "squatch":
                    imports.update(f"squatch.{alias.name}" for alias in node.names)
                elif node.module.startswith("squatch."):
                    imports.add(node.module)
        pending.extend(imports - reachable)
    assert "squatch.rework" not in reachable


def test_update_order_rewrites_the_handoff_ticket_and_requires_review(tmp_path):
    revised = ticket("The updated conflict is resolved.")
    repo, llm, journal, worker = run_rework(
        tmp_path, order(updated_ticket={"ticket": revised}))
    try:
        result = asyncio.run(worker.run(sha=SHA))
    finally:
        journal.close()

    assert result.outcome == "ok" and result.handoff.approval_invalidated is True
    assert (repo / "tickets/original-work/ticket.md").read_text() == revised
    assert lint(repo, "original-work").goal == "The updated conflict is resolved."
    assert [request.surface for request in llm.requests] == ["rework"]
    assert llm.requests[0].worktree is None


def test_split_order_writes_closed_tickets_and_journals_supersedes(tmp_path):
    children = [
        {"stem": "conflict-part-one", "ticket": ticket(
            "The first conflict part is resolved.")},
        {"stem": "conflict-part-two", "ticket": ticket(
            "The second conflict part is resolved.", depends="conflict-part-one")},
    ]
    repo, _, journal, worker = run_rework(
        tmp_path, order(split_tickets=children))
    result = asyncio.run(worker.run(sha=SHA))
    events = tuple(journal.read())
    journal.close()

    assert result.outcome == "ok" and result.handoff.approval_invalidated is True
    for child in children:
        lint(repo, child["stem"])
        meta, _ = parse_frontmatter(
            (repo / f"tickets/{child['stem']}/ticket.md").read_text())
        assert set(meta) <= FRONTMATTER_KEYS and "supersedes" not in meta
    [event] = [event for event in events
               if event.type == "signal" and event.body.get("kind") == SUPERSEDES_SIGNAL]
    assert event.ticket == "original-work"
    assert event.body["supersedes"] == {
        "original-work": ["conflict-part-one", "conflict-part-two"]}


def ladder_config():
    return Config.model_validate({
        "schema_version": 1, "state_dir": ".state",
        "providers": [{"name": "codex", "kind": "cli",
                       "models_by_tier": {"low": "a", "medium": "b",
                                          "high": "c", "max": "c"},
                       "limits": {"concurrency": 1, "est_cost_per_call_usd": 1}}],
        "routing": [{"tier": tier, "surface": "implement",
                     "candidates": [{"provider": "codex"}]}
                    for tier in ("low", "medium", "high", "max")]})


def test_escalation_becomes_diagnosis_and_ladder_selects_the_route(tmp_path):
    response = order(escalation={
        "lessons": ["Use a stronger conflict analysis."],
        "reason": "The unresolved interaction needs more capability."})
    repo, _, journal, worker = run_rework(tmp_path, response)
    before = (repo / "tickets/original-work/ticket.md").read_text()
    try:
        result = asyncio.run(worker.run(sha=SHA))
    finally:
        journal.close()

    assert isinstance(result.diagnosis, DiagnosisRecord)
    assert result.diagnosis.verdict == "escalate"
    config = ladder_config()
    current = Rung("medium", "medium")
    routed = route(config, (), "original-work", "gate_failed", result.diagnosis,
                   current=current)
    assert routed.routed == "ladder"
    assert routed.rung == next_rung(Registry(config), current)
    assert (repo / "tickets/original-work/ticket.md").read_text() == before
    assert "tier" not in result.order.escalation.model_fields_set
    assert "effort" not in result.order.escalation.model_fields_set


def test_rework_waits_for_the_real_mergequeue_outbox_after_slot_unwinds(tmp_path):
    revised = ticket("The post-unwind conflict is resolved.")
    repo, llm, journal, worker = run_rework(
        tmp_path, order(updated_ticket={"ticket": revised}), queued=None)
    queue = queue_with()
    worker._queue = queue

    async def exercise():
        started = asyncio.Event()
        release = asyncio.Event()

        async def unresolved(_candidate):
            assert queue._slot.locked()
            started.set()
            await release.wait()
            item = handoff(run_seq=7)
            return Admission(outcome="rework", conflict_facts=item.facts, rework=item)

        queue._admit = unresolved
        admit = asyncio.create_task(queue.admit(object()))
        await started.wait()
        task = asyncio.create_task(worker.run(sha=SHA))
        await asyncio.sleep(0)
        assert not llm.requests and not task.done()
        release.set()
        admission, result = await asyncio.gather(admit, task)
        assert admission.rework is result.handoff
        assert not queue._slot.locked()
        return result

    try:
        result = asyncio.run(exercise())
    finally:
        journal.close()

    assert ReworkHandoff is UnresolvedConflictHandoff
    assert result.handoff.run_seq == 7
    assert result.handoff.approval_invalidated is True
    assert (repo / "tickets/original-work/ticket.md").read_text() == revised
