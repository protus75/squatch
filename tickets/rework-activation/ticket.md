---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- merge-queue-activation

## Context
- squatch/daemon.py
- squatch/rework.py
- squatch/mergequeue.py
- tests/test_rework.py
- tests/test_daemon_composition.py
- squatch/merge.py

## Plan contract
- section 20

## Goal
Compose Rework against the production pipeline's merge queue and prove post-admission consumption.

## Why
The post-unwind handoff must reach the existing Rework boundary before task lifetimes are introduced.

## Scope in
Add `compose_daemon_rework`, one named composition function in `squatch/daemon.py`, that returns the existing `Rework` with `queue=pipeline.merge_queue`. Its explicit inputs are `repo`, the production pipeline, the production `Driver`, the lock-held `Journal`, the injected `Filesystem`, and the already loaded `specs/rework.md` `Spec`; explicit `tier` and `effort` parameters defaulting to the registry values `medium` and `medium` supply the remaining constructor arguments. Add no config key. The caller supplies these dependencies; composition performs no model call and starts no background loop.

The function's Rework import makes `squatch.rework` reachable from the production-root import closure through the existing squatch.__main__ -> squatch.daemon edge. Do not add a call from `squatch.__main__._locked`: invocation from `_locked` is deferred to the later `background-consumers` boundary, not required to prove this composition function. The in-process harness calls compose_daemon_rework over a pipeline that compose_pipeline really builds and runs the returned worker on that same queue's handoff.

In `squatch/rework.py`, update the dormant-only module contract to identify daemon composition and retain the direct post-admission contracts: update/split/escalate, supersedes, approval invalidation, validated writes and consumption after slot unwind. In `squatch/mergequeue.py`, update the dormant-only module contract to describe the composed queue and its post-unwind Rework consumer; preserve admit and next_rework ordering and the typed handoff. These documentation hooks do not introduce a second queue or new handoff schema.

In `tests/test_rework.py`, migrate `test_rework_remains_unreachable_from_the_production_root` to a positive transitive import-closure proof; preserve `test_spec_is_one_composite_rework_order_surface` and all direct post-admission tests. The construction-owned spec contract stays there: specs/rework.md is neither Context nor fenced because it carries the engine data-block delimiter.

In `tests/test_daemon_composition.py`, exercise compose_daemon_rework over the real composed pipeline with supplied driver/journal/filesystem/spec. Drive that same queue's admit to an unresolved-conflict handoff and prove Rework consumes it only after its serial slot unlocks. Preserve dispatch/config, MergeQueue identity and no-serve proofs.

```yaml
ownership:
  rework-activation:
    owns: []
    hooks:
      - squatch/daemon.py
      - squatch/rework.py
      - squatch/mergequeue.py
      - tests/test_rework.py
      - tests/test_daemon_composition.py
```

## Scope out
Do not edit `squatch/merge.py`, `squatch/__main__.py`, `squatch/runner.py` or `specs/rework.md`. Do not change compose_pipeline, add task lifetimes, config keys, CLI verbs, inline Rework during admission, or duplicate Rework's order/schema/validation behavior.

## Scope fence
- squatch/daemon.py
- squatch/rework.py
- squatch/mergequeue.py
- tests/test_rework.py
- tests/test_daemon_composition.py

## Acceptance criteria
- `squatch/daemon.py` exposes compose_daemon_rework building Rework with explicit repo, pipeline.merge_queue, Driver, lock-held Journal, injected Filesystem, loaded rework Spec and explicit tier/effort defaulting to medium/medium. Construction starts no work; no `__main__._locked` or Runner call site is added and no config key is introduced.
- `tests/test_daemon_composition.py` composes a real pipeline then the worker, drives that same queue's admit, and observes its unresolved handoff consumed only after slot unlock; dispatch/config, queue identity and no-serve proofs pass.
- `tests/test_rework.py` migrates `test_rework_remains_unreachable_from_the_production_root` to prove squatch.rework is reachable from squatch.__main__, preserving `test_spec_is_one_composite_rework_order_surface`, update/split/escalate, supersedes, approval invalidation, validated writes and post-unwind consumption.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_rework.py tests/test_mergequeue.py tests/test_daemon_composition.py tests/test_daemon_admission.py tests/test_daemon_config.py -q
uv run pytest -q
```

## Definition of rejected
Stop if the worker cannot be composed over the real pipeline's queue inside this fence, any required constructor input has no source, or an existing negative assertion lies outside the fence.

## Time budget
- expected: 75m
- stuck: 150m
