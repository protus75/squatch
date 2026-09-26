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
      - squatch/mergequeue.py: no edit; consume MergeQueue.next_rework and UnresolvedConflictHandoff unchanged
```

## Scope out
Do not change merge-queue behavior or make merge-queue test edits. Do not activate Rework, alter queue admission, or implement threshold runtime.

## Scope fence
- squatch/rework.py
- specs/rework.md
- squatch/mergequeue.py
- tests/test_rework.py

## Acceptance criteria
- `tests/test_rework.py` proves update, split, and escalate produce the specified Rework outcomes and records supersedes links without redefining the merge-queue handoff.
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
