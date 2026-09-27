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
- squatch/__main__.py
- eval/shakeout/bench.py
- tests/test_mergequeue.py
- tests/test_merge.py
- tests/test_daemon_composition.py
- tests/test_rework.py

## Plan contract
- section 20

## Goal
Activate red-streak and tree-hash merge admission holds through the shared control boundary.

## Why
Merge holds are independently provable only after pause/resume establishes the single durable release surface.

## Scope in
Inject one `AdmissionHold` into the production `compose_merge_queue` path. In `squatch/__main__.py`, share the lock-held inbox created by the drain control factory with the production pipeline factory for the same journal; never construct or race a second inbox, and remove any `control_inbox=None` fallback. Wire the hold's apply method into that one production control consumer. Update every tracked direct `compose_pipeline` caller for the mandatory dependency: `eval/shakeout/bench.py` constructs its inbox over the bench's existing state directory, journal, and filesystem. A held admission waits without busy-polling or failing the candidate, and in-flight work continues. Journal each hold identity, lifecycle, and trigger before mutation so the operator has a reachable matching release.

Count integration-check red outcomes only. Fire after three distinct stems (K=3), keep repeats such as A,B,A,C counted once, reset on green, and require a fresh streak after a hold fires or releases. A tree-hash mismatch holds immediately. Rebase and regate failures do not count. Matching resume releases exactly the owning hold; stale lifecycle and pre-hold releases are ineffective. Preserve serialization, re-gating, integration checks, and post-unwind Rework publication.

The hold is an optional additive `MergeQueue` hook. Preserve minimal and legacy queue construction that omits the optional attribute, including the unchanged Rework outbox fixture built with `MergeQueue.__new__`; admission must treat an absent hook exactly like `None`, enter the serial slot, and publish its post-unwind handoff without hanging.

```yaml
ownership:
  admission-holds-activation:
    owns: []
    hooks:
    - squatch/mergequeue.py
    - squatch/merge.py
    - squatch/__main__.py
    - eval/shakeout/bench.py
    - tests/test_mergequeue.py
    - tests/test_merge.py
    - tests/test_daemon_composition.py
```

## Scope out
Do not change CLI verbs, dispatch pause behavior, kill/serve behavior, or scheduler policy.

## Scope fence
- squatch/mergequeue.py
- squatch/merge.py
- squatch/__main__.py
- eval/shakeout/bench.py
- tests/test_mergequeue.py
- tests/test_merge.py
- tests/test_daemon_composition.py

## Acceptance criteria
- `tests/test_mergequeue.py` proves three distinct integration reds hold the next admission; A,B,A,C counts correctly; green resets; rebase/regate failures do not count; and every released hold requires a fresh streak.
- `tests/test_mergequeue.py` proves a tree mismatch holds immediately, matching resume releases exactly that hold, stale/pre-hold releases fail closed, and another task progresses while admission waits.
- `tests/test_mergequeue.py` preserves existing serialization, re-gate, integration-check, tree-hash, and Rework-unwind contracts through the production `compose_merge_queue` path.
- `tests/test_merge.py` updates the existing direct `compose_pipeline` construction proof to inject the mandatory shared inbox without restoring a fallback.
- `tests/test_daemon_composition.py` proves the lock holder shares one inbox between dispatch pause and the production merge admission hold, and a matching resume reaches the hold through the one consumer.
- Unchanged `tests/test_rework.py` completes its `test_rework_waits_for_the_real_mergequeue_outbox_after_slot_unwinds` proof, so an absent optional hold on a minimal queue does not block slot entry or Rework publication.
- Unchanged `tests/test_shakeout.py` proves the shakeout benchmark still builds and drives the production pipeline after injecting its state-directory inbox.

## Verification
```
uv run pytest tests/test_mergequeue.py tests/test_merge.py tests/test_daemon_composition.py tests/test_control.py tests/test_rework.py tests/test_shakeout.py -q
uv run pytest -q
```

## Definition of rejected
Stop if the already-activated shared control boundary cannot inject the hold without editing an unfenced path.

## Time budget
- expected: 75m
- stuck: 150m
