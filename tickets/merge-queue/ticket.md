---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: high
agent_effort: high
---
## Depends on
- phase3-continue

## Context
- squatch/merge.py
- squatch/git.py
- squatch/config.py

## Plan contract
- section 20

## Goal
Construct the dormant serial merge admission queue with its conflict facts and two typed resolution rungs.

## Why
The section 20 registry makes merge admission a KNOWN-DEEP construction boundary: it must re-gate the rebased candidate before integration, preserve current Phase 1 composition, and leave unresolved work for Rework only after admission has unwound.

## Scope in
Build `squatch/mergequeue.py` as the registry owner for the dormant serial admission task, post-rebase re-gate orchestration, integration check, candidate tree-hash assertion, conflict-facts record, and both typed resolution rungs. Rung 1 is a mechanical in-queue resolution of a fixture conflict; rung 2 is a typed unresolved-conflict handoff record emitted after unwind and consumed by later Rework without redefining it. Add only `compose_merge_queue` to `squatch/merge.py`; add public Git operations that stop a rebase at conflict, list conflicted paths, and continue the rebase while leaving `rebase` and `rebase_abort` unchanged.

```yaml
ownership:
  merge-queue:
    owns:
      - squatch/mergequeue.py
      - tests/test_mergequeue.py
    contract: dormant serial admission, post-rebase re-gate, integration check, candidate tree-hash assertion, conflict facts, mechanical resolution, and typed unresolved-conflict handoff
    hooks:
      - squatch/merge.py: compose_merge_queue
      - squatch/git.py: rebase_stop_at_conflict
      - squatch/git.py: conflicted_paths
      - squatch/git.py: rebase_continue
```

## Scope out
Do not activate the queue or change the current `Merge`, `Pipeline`, or `compose_pipeline` behavior. Do not change tested existing behavior, `rebase`, or `rebase_abort`; do not import `squatch.scheduler` or `squatch.watcher`; do not add pause or hold behavior, which activates later with pause-resume.

## Scope fence
- squatch/mergequeue.py
- squatch/merge.py
- squatch/git.py
- tests/test_mergequeue.py

## Acceptance criteria
- `tests/test_mergequeue.py` proves serial dormant admission performs post-rebase re-gate and the integration check, then asserts the candidate tree hash before integration.
- `tests/test_mergequeue.py` proves the additive `compose_merge_queue` hook leaves current `Merge`, `Pipeline`, and `compose_pipeline` behavior unchanged, and `squatch/git.py` exposes only stop-at-conflict, conflicted-path listing, and rebase-continue additions while preserving `rebase` and `rebase_abort`.
- `tests/test_mergequeue.py` resolves a fixture conflict through the mechanical in-queue rung and records its conflict facts; an unresolved conflict unwinds admission before emitting the typed Rework handoff that Rework consumes without redefining.
- `tests/test_mergequeue.py` proves a candidate tree-hash mismatch refuses only that candidate with a typed finding and paved road, leaves main untouched, unwinds admission, releases the serial slot, and creates no pause or hold.
- `squatch/mergequeue.py` imports neither `squatch.scheduler` nor `squatch.watcher`.
- `uv run pytest tests/test_mergequeue.py -q` exits 0.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_mergequeue.py -q
uv run pytest -q
```

## Definition of rejected
Stop if the additive Git seam cannot stop, inspect, and continue a conflict without changing `rebase` or `rebase_abort`, if a tested current composition assertion must change, or if the queue needs scheduler or watcher reachability.

## Time budget
- expected: 120m
- stuck: 180m
