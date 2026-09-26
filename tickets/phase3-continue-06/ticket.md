---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- scheduler-activation

## Context
- tests/test_seeded_phase3_04.py
- squatch/config.py
- tests/test_daemon_admission.py
- tests/test_daemon_config.py
- tests/test_mergequeue.py
- tests/test_rework.py

## Plan contract
- section 20

## Goal
Author merge-queue and rework activation seeds and the next shrinking Phase 3 continuation.

## Why
The scheduler composition harness is now established, so the two post-admission activations can be independently proved against it.

## Scope in
Read the merged `tests/test_daemon_composition.py`, `squatch/daemon.py`, and `tests/test_scheduler.py` before authoring. Author exactly `tickets/merge-queue-activation/ticket.md`, `tickets/rework-activation/ticket.md`, and `tickets/phase3-continue-07/ticket.md` as uncommitted confirmed seed files, plus committed `tests/test_seeded_phase3_06.py`. The activation tickets depend in registry order on `phase3-continue-06` and are medium/medium with expected/stuck budgets 75m/150m; `phase3-continue-07` depends on both activations, is medium/medium with the same budgets, and fences exactly `tickets` and `tests/test_seeded_phase3_07.py`.

`merge-queue-activation` fences `squatch/daemon.py`, `squatch/mergequeue.py`, `squatch/merge.py`, `squatch/git.py`, `tests/test_mergequeue.py`, and `tests/test_daemon_composition.py`; it hooks every existing path and owns no new path. Its Context includes the then-existing composition harness. It migrates `test_additive_composition_hook_does_not_change_phase1_composition`'s literal `not hasattr(pipeline, "merge_queue")` dormancy assertion and preserves `test_mergequeue_has_no_scheduler_or_watcher_dependency`.

`rework-activation` depends on `merge-queue-activation`, fences `squatch/daemon.py`, `squatch/rework.py`, `squatch/mergequeue.py`, `tests/test_rework.py`, and `tests/test_daemon_composition.py`; it hooks every existing path and owns no new path. Its Context includes the then-existing composition harness. The construction-owned spec contract remains proved by `test_spec_is_one_composite_rework_order_surface`, so the delimiter-bearing `specs/rework.md` is neither fenced nor Context. It migrates `test_rework_remains_unreachable_from_the_production_root`, which asserts `squatch.rework` is outside the `squatch.__main__` import closure, while preserving Rework's direct post-admission contracts.

```yaml
ownership:
  merge-queue-activation:
    owns: []
    hooks:
      - squatch/daemon.py
      - squatch/mergequeue.py
      - squatch/merge.py
      - squatch/git.py
      - tests/test_mergequeue.py
      - tests/test_daemon_composition.py
  rework-activation:
    owns: []
    hooks:
      - squatch/daemon.py
      - squatch/rework.py
      - squatch/mergequeue.py
      - tests/test_rework.py
      - tests/test_daemon_composition.py
  phase3-continue-07:
    owns:
      - tickets
      - tests/test_seeded_phase3_07.py
    hooks: []
```

The finite ordered admissions this continuation carries are:
```yaml
- [merge-queue-activation, rework-activation]
- [background-consumers, control-inbox]
- [dispatch-pause-boundary, pause-resume-activation]
- [kill-signal-journal, kill-executor-abort]
- [kill-worker-stop, kill-failure-suppression]
- [kill-cli-activation]
- [heartbeat]
- [restart-timers]
- [flake-detection, flake-release]
- [journal-roll, storm-ledger]
- [storm-producer-wiring, storm-notification-activation]
- [storm-dispatch-hold]
- [checkpoint-push]
- [daemon-soak]
- [soak-run]
- [phase3-exit]
```

The successor continuation carries:
```yaml
- [background-consumers, control-inbox]
- [dispatch-pause-boundary, pause-resume-activation]
- [kill-signal-journal, kill-executor-abort]
- [kill-worker-stop, kill-failure-suppression]
- [kill-cli-activation]
- [heartbeat]
- [restart-timers]
- [flake-detection, flake-release]
- [journal-roll, storm-ledger]
- [storm-producer-wiring, storm-notification-activation]
- [storm-dispatch-hold]
- [checkpoint-push]
- [daemon-soak]
- [soak-run]
- [phase3-exit]
```

## Scope out
Do not implement either activation, author beyond `phase3-continue-07`, change production code, or include prompt-spec sources carrying the engine data-block delimiter in Context.

## Scope fence
- tickets
- tests/test_seeded_phase3_06.py

## Acceptance criteria
- `tests/test_seeded_phase3_06.py` proves the exact emitted identities, edges, tiers, budgets, fences, keyed ownership, Context closure, predecessor-test closure, render headroom, and shrinking suffix.
- `tests/test_seeded_phase3_06.py` proves every existing fence path is Context for its activation seed and both later activation seeds include the merged `tests/test_daemon_composition.py` harness in Context.
- `tests/test_seeded_phase3_06.py` proves the merge activation names and migrates the literal `not hasattr(pipeline, "merge_queue")` assertion while preserving `test_mergequeue_has_no_scheduler_or_watcher_dependency`, and that the rework activation names and migrates `test_rework_remains_unreachable_from_the_production_root` while preserving `test_spec_is_one_composite_rework_order_surface` and its direct post-admission contracts.
- `tests/test_seeded_phase3_06.py` uses a pinned authoring-time Context map that lists `tests/test_daemon_composition.py` as existing and only `tests/test_seeded_phase3_07.py` as new, not later live file bytes, for synthetic renders; it proves no Context includes a delimiter-carrying prompt-spec source.
- `uv run pytest tests/test_seeded_phase3_06.py -q` exits 0.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_seeded_phase3_06.py -q
uv run pytest -q
```

## Definition of rejected
Stop if either activation cannot independently prove real production composition, a predecessor assertion falls outside its fence, the successor duplicates the activation pair, or a seed exceeds requisition headroom.

## Time budget
- expected: 75m
- stuck: 150m
