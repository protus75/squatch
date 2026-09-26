---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- thresh-runtime

## Context
- tickets/phase3-continue-03/ticket.md
- tests/test_seeded_phase3_core.py

## Plan contract
- section 20

## Goal
Author the dispatch-admission boundary, dispatch-config snapshot, and the next continuation while carrying the remaining ordered Phase 3 admissions.

## Why
The finite section 20 partition advances from threshold runtime to the dispatch-admission pair, preserving one independently provable boundary per ticket and a shrinking continuation suffix.

## Scope in
Author exactly `tickets/dispatch-admission-boundary/ticket.md`, `tickets/dispatch-config-snapshot/ticket.md`, and `tickets/phase3-continue-05/ticket.md` as uncommitted confirmed seed files, plus committed `tests/test_seeded_phase3_04.py`. The dispatch pair are medium/medium construction tickets in registry order: `dispatch-admission-boundary` depends on `phase3-continue-04`, `dispatch-config-snapshot` depends on `dispatch-admission-boundary`, and `phase3-continue-05` depends on `dispatch-config-snapshot`. Map every new path in their exact fences to the section 20 registry owner or hook, including `squatch/daemon.py`, `squatch/config.py`, `tests/test_daemon_admission.py`, and `tests/test_daemon_config.py`. Every fence path that exists on main is Context, and no dispatch-pair fence may invalidate an existing test assertion unless that test is fenced. The successor is medium/medium and fences exactly `tickets` and `tests/test_seeded_phase3_05.py`.

The finite ordered admissions this continuation carries are:
```yaml
- [dispatch-admission-boundary, dispatch-config-snapshot]
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

## Scope out
Do not implement dispatch admission, config snapshotting, scheduler activation, or later Phase 3 work. Do not author a seed beyond the dispatch pair and `phase3-continue-05`, change production code, or alter existing tests.

## Scope fence
- tickets
- tests/test_seeded_phase3_04.py

## Acceptance criteria
- `tests/test_seeded_phase3_04.py` proves the emitted set is exactly `dispatch-admission-boundary`, `dispatch-config-snapshot`, and `phase3-continue-05`, all lint as confirmed section-20 seed tickets with the exact dependency chain and a batch within `seeding.max_seeds_per_admission`.
- `tests/test_seeded_phase3_04.py` pins every emitted ticket at medium/medium with source seed, state confirmed, exact expected/stuck budgets, expected less than stuck, and stuck at or below `drain.max_ticket_minutes`.
- `tests/test_seeded_phase3_04.py` pins each exact fence and keyed ownership record, mapping `squatch/daemon.py`, `squatch/config.py`, `tests/test_daemon_admission.py`, and `tests/test_daemon_config.py` to the registry boundary that owns or hooks it.
- `tests/test_seeded_phase3_04.py` asserts every fence path that exists on main is in that seed's Context and proves predecessor-test closure: no dispatch-pair fence invalidates an existing test assertion unless that test is also fenced.
- `tests/test_seeded_phase3_04.py` uses pinned authoring-time Context bytes only for synthetic render sizing, checks every Implement render against requisition headroom, and proves `phase3-continue-05` carries the structured YAML suffix from `scheduler-activation` through `phase3-exit` in registry order.
- `uv run pytest tests/test_seeded_phase3_04.py -q` exits 0.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_seeded_phase3_04.py -q
uv run pytest -q
```

## Definition of rejected
Stop if the dispatch pair cannot be separated into independently provable tickets, if predecessor-test closure requires a path outside the registry fence, if the shrinking suffix duplicates the dispatch pair, or if an emitted ticket cannot fit requisition headroom.

## Time budget
- expected: 75m
- stuck: 150m
