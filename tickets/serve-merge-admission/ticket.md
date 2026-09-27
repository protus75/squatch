---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: high
agent_effort: high
---
## Depends on
- phase3-continue-21
- serve-activation

## Context
- squatch/merge.py
- squatch/serve.py
- tests/test_merge.py
- tests/test_serve.py

## Plan contract
- section 20

## Goal
Route settled production Serve deliveries through the serial MergeQueue while preserving bootstrap drain admission.

## Why
The daemon-soak-runner premise audit proved that production Serve dispatch reaches `Pipeline.run`, but that method still invokes Phase 1 `Merge.admit` directly. The composed MergeQueue is reachable only by Rework, so its two conflict-resolution rungs and post-rebase integration check cannot be exercised by production work.

## Scope in
Add an explicit daemon-admission mode owned by `squatch/merge.py` and selected only by `Serve.compose` in `squatch/serve.py`. Bootstrap `drain` keeps the existing inline `Merge.admit` path and never gains daemon admission holds.

In daemon mode, a settled `Pipeline.run` performs the existing code-lane and seed-safety prechecks, constructs exactly one real `Candidate`, and offers it to the composed `MergeQueue`. The queue owns rebase, both conflict-resolution rungs, post-rebase mechanical regate, integration verification, red-streak/tree-hash holds, and integration. A successful queue admission retires the worktree and branch and writes the existing `to: merged` transition and merge log exactly once with the real commit and reviewed SHA. A `gate_failed` or `rework` result leaves main and the branch intact, preserves typed findings or handoff, and never retires. Rework consumes its handoff only after the queue slot unwinds.

`tests/test_merge.py` and `tests/test_serve.py` drive a settled delivery through the real Serve-selected `Pipeline.run` path and prove the queue is reached without calling `MergeQueue.admit` from a harness. They preserve an unchanged bootstrap-inline regression. `tests/test_mergequeue.py` pins both rungs, integration-red, tree hash, holds, and post-unwind Rework; it is a fenced on-demand inspection exception because embedding it with both production roots and the other tests breaches `REQ_RENDER_HEADROOM`.

## Scope out
Do not change bootstrap drain admission, call the queue directly from the soak harness, weaken approval/code-lane/seed-safety checks, duplicate merge transitions, run Rework while the queue slot is held, or implement the soak runner here.

## Scope fence
- squatch/merge.py
- squatch/serve.py
- tests/test_merge.py
- tests/test_mergequeue.py
- tests/test_serve.py

## Acceptance criteria
- `tests/test_serve.py` proves `Serve.compose` selects daemon admission and a settled production dispatch reaches the composed MergeQueue through `Pipeline.run`, with no direct harness admission.
- `tests/test_merge.py` proves bootstrap `Pipeline.run` still uses inline `Merge.admit`, while daemon mode preserves code-lane and seed-safety checks and finalizes one successful queue admission with exactly one retirement, `to: merged` transition, merge log, real commit, and reviewed SHA.
- `tests/test_mergequeue.py` proves daemon-mode conflict handling reaches both resolution rungs, integration-red leaves main green and the branch intact, and Rework consumes only after the queue slot unwinds.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_merge.py tests/test_mergequeue.py tests/test_serve.py -q
uv run pytest -q
```

## Definition of rejected
Reject a daemon path that still bypasses MergeQueue, any bootstrap behavior change, direct harness admission, lost precheck, duplicate finalization, branch retirement on failure/rework, or inline Rework under the queue slot.

## Time budget
- expected: 90m
- stuck: 180m
