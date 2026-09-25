---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- merge-queue

## Context
- squatch/tickets.py
- squatch/config.py
- config.yaml
- squatch/merge.py
- tests/test_seeded_phase3_core.py

## Plan contract
- section 20

## Goal
Author the known-deep Rework construction seed and the next continuation, carrying the remaining ordered Phase 3 admissions.

## Why
Section 20 requires each continuation to advance one finite admission and carry a shrinking unseeded suffix. This continuation's own carried remainder begins with the Rework boundary it seeds; its successor begins at threshold runtime.

## Scope in
Author exactly `tickets/rework-stage/ticket.md` and `tickets/phase3-continue-03/ticket.md` as uncommitted confirmed seed files, plus committed `tests/test_seeded_phase3_02.py`. The emitted `rework-stage` is high/high, depends on `phase3-continue-02`, fences `squatch/rework.py`, `specs/rework.md`, `squatch/mergequeue.py`, and `tests/test_rework.py`, and owns update/split/escalate and supersedes after merge-queue admission unwinds. Its Scope out forbids merge-queue behavior or test edits and its Verification runs `uv run pytest tests/test_mergequeue.py -q`. The emitted `phase3-continue-03` is medium/medium, depends on `rework-stage`, and fences only `tickets` and `tests/test_seeded_phase3_03.py`; its structured Scope in carries the suffix from `thresh-runtime` through `phase3-exit`.

```yaml
ownership:
  rework-stage:
    owns:
      - squatch/rework.py
      - specs/rework.md
      - tests/test_rework.py
    hooks:
      - squatch/mergequeue.py
```

The finite ordered admissions this continuation carries are:
```yaml
- [rework-stage]
- [thresh-runtime]
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

## Scope out
Do not implement Rework, merge-queue activation, threshold runtime, or later Phase 3 work. Do not author a seed beyond `rework-stage` and `phase3-continue-03`, change production code, or alter existing tests.

## Scope fence
- tickets
- tests/test_seeded_phase3_02.py

## Acceptance criteria
- `tests/test_seeded_phase3_02.py` proves the emitted set is exactly `rework-stage` and `phase3-continue-03`, both lint as confirmed seed tickets citing section 20 alone, with edges `phase3-continue-02 -> rework-stage -> phase3-continue-03` and a batch within `seeding.max_seeds_per_admission`.
- `tests/test_seeded_phase3_02.py` pins rework-stage at high/high with fence `squatch/rework.py`, `specs/rework.md`, `squatch/mergequeue.py`, `tests/test_rework.py`, and phase3-continue-03 at medium/medium with fence `tickets`, `tests/test_seeded_phase3_03.py`.
- `tests/test_seeded_phase3_02.py` pins expected and stuck minutes for both emitted seeds with expected less than stuck and stuck at or below `drain.max_ticket_minutes`.
- `tests/test_seeded_phase3_02.py` checks the keyed `rework-stage` ownership record, every existing authoring-time fence path in Context using pinned `EXISTING_AT_AUTHORING` bytes, and each Implement render under `RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM`.
- `tests/test_seeded_phase3_02.py` proves rework-stage Scope out forbids merge-queue behavior and test edits, its Verification includes `uv run pytest tests/test_mergequeue.py -q`, and phase3-continue-03's structured YAML suffix equals the ordered tuple from `thresh-runtime` through `phase3-exit` parsed as in `tests/test_seeded_phase3_core.py`.
- `uv run pytest tests/test_seeded_phase3_02.py -q` exits 0.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_seeded_phase3_02.py -q
uv run pytest -q
```

## Definition of rejected
Stop if the shrinking suffix cannot be represented without duplicating Rework, if Rework needs a merge-queue behavior or test edit, if an emitted ticket cannot fit requisition headroom, or if a required path lies outside this fence.

## Time budget
- expected: 75m
- stuck: 150m
