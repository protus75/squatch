---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- phase3-continue-18

## Context
- squatch/daemon.py
- squatch/git.py
- tests/test_git.py

## Plan contract
- section 20

## Goal
Durably push a checkpoint through the Git seam.

## Why
The production storm hold is complete; checkpoint durability is the next independently provable boundary.

## Scope in
Add `squatch/checkpoint.py` and `tests/test_checkpoint.py`. Add one public argv-only Git push operation in `squatch/git.py`, with its direct seam test in `tests/test_git.py`. Migrate only `tests/test_mergequeue.py::test_git_conflict_seams_are_only_additions_and_old_rebase_still_aborts`'s public-operation allowlist to admit `push`, preserving every conflict/rebase assertion. `tests/test_mergequeue.py` is a fenced on-demand inspection exception rather than embedded Context because embedding that large predecessor suite breaches requisition headroom. Compose checkpoint pushing through that seam in `squatch/daemon.py`. Persist enough checkpoint state so restart re-fires an incomplete push after restart without duplicating a completed push; composition calls only that seam.

## Scope out
Do not add a raw subprocess call, change unrelated Git operations, or implement daemon soak work.

## Scope fence
- squatch/checkpoint.py
- tests/test_checkpoint.py
- squatch/daemon.py
- squatch/git.py
- tests/test_git.py
- tests/test_mergequeue.py

## Acceptance criteria
- `tests/test_git.py` proves the public push seam uses only a dir-pinned argv invocation through the process seam.
- `tests/test_checkpoint.py` proves daemon composition invokes that seam and never bypasses it.
- `tests/test_checkpoint.py` proves restart re-fires an incomplete push and does not duplicate a completed push.
- The named `tests/test_mergequeue.py` test admits only the new `push` public operation while preserving its conflict/rebase assertions.

## Verification
```
uv run pytest tests/test_checkpoint.py tests/test_git.py tests/test_daemon_composition.py -q
uv run pytest tests/test_mergequeue.py::test_git_conflict_seams_are_only_additions_and_old_rebase_still_aborts -q
uv run pytest -q
```

## Definition of rejected
Reject a raw Git invocation, a push without a direct seam test, duplicate completed push, or unretried incomplete push.

## Time budget
- expected: 75m
- stuck: 150m
