---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: high
agent_effort: high
---
## Depends on
- serve-merge-admission

## Context
- squatch/reconcile.py
- tests/test_reconcile.py

## Plan contract
- section 20

## Goal
Record a durable run-scoped recovery alert when entry reconciliation abandons an orphan.

## Why
Production currently journals the abandoned terminal and cleanly redispatches the stem, but writes no Box or alert record naming the recovered run. The closed daemon-soak schema therefore cannot derive the killed-worker disposition or producing run without manufacturing a later failure.

## Scope in
For every orphan actually reaped by `reconcile`, append exactly one durable `signal` for that orphan's ticket and run sequence immediately after its `abandoned` state transition and before worktree removal. Its body has kind `recovery_alert`, disposition `alert`, outcome `abandoned`, and a reason identifying entry reconciliation. Preserve the existing terminal-before-removal order and redispatch behavior. Prove exact event ordering and provenance for present and already-absent worktrees, and prove a later restart does not duplicate the alert because the terminal removed the run from the orphan fold.

The exact embedded Context and fence are `squatch/reconcile.py` and `tests/test_reconcile.py`.

## Scope out
Do not relabel lifecycle control decisions, create Box mail, change ordinary failure routing, change the report schema, alter orphan detection or redispatch, implement the soak runner, or touch daemon composition.

## Scope fence
- squatch/reconcile.py
- tests/test_reconcile.py

## Acceptance criteria
- `tests/test_reconcile.py` proves each reaped orphan gets one `recovery_alert` signal immediately after its matching `abandoned` transition and before worktree removal, with exact ticket and run-sequence provenance, disposition `alert`, outcome `abandoned`, and an entry-reconciliation reason.
- `tests/test_reconcile.py` proves the same contract when the orphan worktree is already absent and proves a second reconciliation emits no duplicate terminal or alert.
- `tests/test_reconcile.py` preserves existing orphan harvest, removal, pruning, reporting, and redispatch behavior.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_reconcile.py -q
uv run pytest -q
```

## Definition of rejected
Reject an unscoped alert, a missing or synthetic run sequence, alert-before-terminal or alert-after-removal ordering, duplicate restart alert, Box mail, lifecycle-decision relabeling, or any redispatch behavior change.

## Time budget
- expected: 75m
- stuck: 150m
