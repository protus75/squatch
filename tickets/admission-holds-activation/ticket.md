---
state: confirmed
source: human
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- pause-resume-activation

## Context
- tests/test_seeded_phase3_core.py
- squatch/control.py
- squatch/mergequeue.py
- squatch/merge.py
- tests/test_mergequeue.py

## Plan contract
- section 20

## Goal
Activate red-streak and tree-hash merge admission holds through the shared control boundary.

## Why
Merge holds are independently provable only after pause/resume establishes the single durable release surface.

## Scope in
Inject one `AdmissionHold` into the production `compose_merge_queue` path; reuse the engine-owned control lifecycle and never construct or race a second inbox. A held admission waits without busy-polling or failing the candidate, and in-flight work continues. Journal each hold identity, lifecycle, and trigger before mutation so the operator has a reachable matching release.

Count integration-check red outcomes only. Fire after three distinct stems (K=3), keep repeats such as A,B,A,C counted once, reset on green, and require a fresh streak after a hold fires or releases. A tree-hash mismatch holds immediately. Rebase and regate failures do not count. Matching resume releases exactly the owning hold; stale lifecycle and pre-hold releases are ineffective. Preserve serialization, re-gating, integration checks, and post-unwind Rework publication.

```yaml
ownership:
  admission-holds-activation:
    owns: []
    hooks:
    - squatch/mergequeue.py
    - squatch/merge.py
    - tests/test_mergequeue.py
```

## Scope out
Do not change CLI verbs, dispatch pause behavior, kill/serve behavior, or scheduler policy.

## Scope fence
- squatch/mergequeue.py
- squatch/merge.py
- tests/test_mergequeue.py

## Acceptance criteria
- `tests/test_mergequeue.py` proves three distinct integration reds hold the next admission; A,B,A,C counts correctly; green resets; rebase/regate failures do not count; and every released hold requires a fresh streak.
- `tests/test_mergequeue.py` proves a tree mismatch holds immediately, matching resume releases exactly that hold, stale/pre-hold releases fail closed, and another task progresses while admission waits.
- `tests/test_mergequeue.py` preserves existing serialization, re-gate, integration-check, tree-hash, and Rework-unwind contracts through the production `compose_merge_queue` path.

## Verification
```
uv run pytest tests/test_mergequeue.py tests/test_daemon_composition.py tests/test_control.py -q
uv run pytest -q
```

## Definition of rejected
Stop if the already-activated shared control boundary cannot inject the hold without editing an unfenced path.

## Time budget
- expected: 75m
- stuck: 150m
