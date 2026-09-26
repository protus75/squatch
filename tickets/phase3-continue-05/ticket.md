---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- dispatch-config-snapshot

## Context
- tickets/phase3-continue-04/ticket.md
- tests/test_seeded_phase3_core.py
- tests/test_seeded_phase3_04.py
- squatch/specs.py
- squatch/requisition.py
- squatch/config.py
- squatch/scheduler.py
- squatch/watcher.py
- squatch/__main__.py
- tests/test_scheduler.py
- tests/test_daemon_admission.py
- tests/test_daemon_config.py

## Plan contract
- section 20

## Goal
Author the known-deep scheduler activation seed and the next continuation, carrying the remaining ordered Phase 3 admissions.

## Why
The finite section 20 partition advances from dormant dispatch construction to the first production composition, with a reusable in-process harness for later activations.

## Scope in
Author exactly `tickets/scheduler-activation/ticket.md` and `tickets/phase3-continue-06/ticket.md` as uncommitted confirmed seed files, plus committed `tests/test_seeded_phase3_05.py`. `scheduler-activation` depends on `phase3-continue-05`, is high/high, has expected/stuck budgets of 120m/180m, and fences exactly `squatch/daemon.py`, `squatch/scheduler.py`, `squatch/watcher.py`, `squatch/__main__.py`, `tests/test_scheduler.py`, `tests/test_daemon_admission.py`, `tests/test_daemon_composition.py`. `phase3-continue-06` depends on `scheduler-activation`, is medium/medium with 75m/150m budgets, and fences exactly `tickets` and `tests/test_seeded_phase3_06.py`.

The activation seed lands the reusable in-process production-composition harness in `tests/test_daemon_composition.py`. Its evidence constructs the real CLI/serve object graph without launching serve, drives single-flight dispatch through the constructed scheduler/watcher and admission boundary, proves watcher reprioritization and per-dispatch config capture, and migrates both the existing `test_scheduler_and_watcher_are_unreachable_from_the_production_root` negative assertion in `tests/test_scheduler.py` and the global `squatch.daemon` absence assertion in `tests/test_daemon_admission.py` to positive production reachability. Preserve the direct scheduling/import-scanner fixtures and the local dispatch contracts in `tests/test_daemon_admission.py` and `tests/test_daemon_config.py`. Do not seed background consumers, control verbs, merge/rework activation, or their holds here.

The emitted `phase3-continue-06` Context includes `tests/test_seeded_phase3_04.py`, `squatch/specs.py`, `squatch/requisition.py`, `squatch/config.py`, `tests/test_daemon_admission.py`, `tests/test_daemon_config.py`, and the then-merged composition harness alongside the merge/rework construction paths. It states that `merge-queue-activation` migrates `test_additive_composition_hook_does_not_change_phase1_composition`'s literal `not hasattr(pipeline, "merge_queue")` assertion, preserves `test_mergequeue_has_no_scheduler_or_watcher_dependency`, and pins both facts in `tests/test_seeded_phase3_06.py`.

```yaml
ownership:
  scheduler-activation:
    owns:
      - tests/test_daemon_composition.py
    hooks:
      - squatch/daemon.py
      - squatch/scheduler.py
      - squatch/watcher.py
      - squatch/__main__.py
      - tests/test_scheduler.py
      - tests/test_daemon_admission.py
  phase3-continue-06:
    owns:
      - tickets
      - tests/test_seeded_phase3_06.py
    hooks: []
```

The finite ordered admissions this continuation carries are:
```yaml
- [scheduler-activation]
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

## Scope out
Do not implement scheduler activation or later Phase 3 work, author another seed, change production code, or alter existing tests. Do not include this ticket's newly created test as emitted Context before it is merged.

## Scope fence
- tickets
- tests/test_seeded_phase3_05.py

## Acceptance criteria
- `tests/test_seeded_phase3_05.py` proves the emitted set is exactly `scheduler-activation` and `phase3-continue-06`, both lint as confirmed source-seed tickets citing section 20 alone, with exact edges `phase3-continue-05 -> scheduler-activation -> phase3-continue-06` and a batch within `seeding.max_seeds_per_admission`.
- `tests/test_seeded_phase3_05.py` pins scheduler-activation at high/high with expected/stuck minutes 120m/180m and phase3-continue-06 at medium/medium with 75m/150m; each expected value is less than stuck and each stuck value is at or below `drain.max_ticket_minutes`.
- `tests/test_seeded_phase3_05.py` pins each exact fence and keyed ownership record from Scope in, including the new composition harness and the existing production hooks. The emitted activation requires in-process real production composition and explicitly migrates the predecessor scheduler reachability assertion.
- `tests/test_seeded_phase3_05.py` pins an `EXISTING_AT_AUTHORING` map from main when these seeds are authored, including the then-merged `squatch/daemon.py`, `tests/test_daemon_admission.py`, and `tests/test_daemon_config.py`, plus every existing Context or fence file it names. It requires `set(context) <= EXISTING_AT_AUTHORING` and requires every fence entry in that map to appear in that seed's Context. Never check live existence on main in the lasting test: new owner paths, including `tests/test_daemon_composition.py`, remain outside this pinned map after later merges. Use this same map as the source of synthetic render sizes; do not compare its pinned sizes with later live bytes.
- `tests/test_seeded_phase3_05.py` proves predecessor-test closure: no scheduler-activation fence path invalidates an existing test assertion unless that test is also fenced. Name both the `tests/test_scheduler.py` reachability assertion and `tests/test_daemon_admission.py` global daemon-absence assertion as migrations owned by scheduler activation, and prove the remaining local dispatch contracts in `tests/test_daemon_admission.py` and `tests/test_daemon_config.py` survive unchanged.
- `tests/test_seeded_phase3_05.py` renders every emitted Implement prompt with pinned authoring-time Context sizes under `RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM`, following `tests/test_seeded_phase3_core.py`. Check actual Context for renderer delimiters while authoring, without making future file content a lasting test invariant.
- `tests/test_seeded_phase3_05.py` proves phase3-continue-06 carries the structured YAML suffix from merge-queue-activation through phase3-exit in registry order, with no scheduler-activation duplicate, and gives that continuation the same identity, tier/budget, pinned authoring-time Context closure, ownership, predecessor-test closure, render-headroom, and shrinking-suffix obligations. It pins the required seeded-pattern/render/config and daemon dispatch Context paths, the exact merge-queue dormancy assertion migration, and the preserved scheduler/watcher dependency constraint.
- `uv run pytest tests/test_seeded_phase3_05.py -q` exits 0.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_seeded_phase3_05.py -q
uv run pytest -q
```

## Definition of rejected
Stop if scheduler activation cannot be independently proved through real production composition, if predecessor-test closure requires a path outside the registry fence, if the shrinking suffix duplicates scheduler activation, or if either emitted seed cannot fit requisition headroom.

## Time budget
- expected: 75m
- stuck: 150m
