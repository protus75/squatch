---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: high
agent_effort: high
---
## Depends on
- phase3-continue-02

## Context
- squatch/mergequeue.py
- tests/test_mergequeue.py
- squatch/tickets.py
- squatch/ladder.py
- squatch/reject.py
- squatch/journal.py
- squatch/llm.py

## Plan contract
- section 20

## Goal
Construct the dormant Rework boundary that updates, splits, and escalates unresolved work after merge admission has unwound.

## Why
The section 20 registry assigns one known-deep boundary to Rework, after the merge queue has released its serial admission slot and recorded an unresolved handoff.

## Scope in
Build `squatch/rework.py` and `specs/rework.md` as the owners of update, split, escalate, and supersedes behavior. Consume `MergeQueue.next_rework()` and import `UnresolvedConflictHandoff` unchanged after admission unwinds; the `squatch/mergequeue.py` hook permits no edit. Add `tests/test_rework.py` for the Rework behavior.

```yaml
ownership:
  rework-stage:
    owns:
      - squatch/rework.py
      - specs/rework.md
      - tests/test_rework.py
    hooks:
      - squatch/mergequeue.py
```

## Scope out
Do not change merge-queue behavior or make merge-queue test edits. Do not activate Rework, alter queue admission, or implement threshold runtime.

## Scope fence
- squatch/rework.py
- specs/rework.md
- squatch/mergequeue.py
- tests/test_rework.py

## Acceptance criteria
- `tests/test_rework.py` proves `specs/rework.md` loads through squatch.specs.load_spec as surface `rework` with one composite rework-order emits type; the existing LLM_SURFACES already admits `rework`.
- `tests/test_rework.py` drives squatch.llm.FakeLLM through an update order and observes a lint-valid updated ticket for the handoff stem.
- `tests/test_rework.py` drives FakeLLM through a split order and observes lint-valid child tickets carrying only the closed FRONTMATTER_KEYS from squatch.tickets, plus a journal `signal` event containing a supersedes map from the old stem to the child stems. Supersedes is journal data, never a new frontmatter key.
- `tests/test_rework.py` drives FakeLLM through an escalate order and observes a diagnosis-shaped `escalate` verdict represented as DiagnosisRecord. Passing that record to squatch.reject.route with an available next rung returns a ladder route selected by squatch.ladder.next_rung; neither module is edited. The Rework escalation element names no tier or effort, and ticket frontmatter stays unchanged.
- `tests/test_rework.py` proves every consumed UnresolvedConflictHandoff retains approval_invalidated=True, requiring review again for the resulting work.
- `tests/test_rework.py` proves Rework consumes `MergeQueue.next_rework()` and `UnresolvedConflictHandoff` only after admission has unwound.
- `tests/test_mergequeue.py` exits 0 unedited, proving the `squatch/mergequeue.py` hook has no behavior or test edit.
- `uv run pytest tests/test_rework.py -q` exits 0.
- `uv run pytest tests/test_mergequeue.py -q` exits 0.

## Verification
```
uv run pytest tests/test_rework.py -q
uv run pytest tests/test_mergequeue.py -q
uv run pytest -q
```

## Definition of rejected
Stop if Rework requires a merge-queue behavior or test edit, if it cannot consume the existing handoff after unwind, or if any required path lies outside this fence.

## Time budget
- expected: 120m
- stuck: 180m
