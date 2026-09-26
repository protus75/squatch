---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- rework-stage

## Context
- squatch/tickets.py
- squatch/config.py
- config.yaml
- squatch/providers.py
- tests/test_providers.py

## Plan contract
- section 20

## Goal
Author the known-deep threshold-runtime seed and the next continuation, carrying the remaining ordered Phase 3 admissions.

## Why
The finite section 20 partition advances from Rework to threshold runtime. The successor starts with the dispatch-admission pair, preserving one independently reviewable construction boundary per admission.

## Scope in
Author exactly `tickets/thresh-runtime/ticket.md` and `tickets/phase3-continue-04/ticket.md` as uncommitted confirmed seed files, plus committed `tests/test_seeded_phase3_03.py`. `thresh-runtime` depends on `rework-stage`, is high/high, has expected/stuck budgets of 120m/180m, and its exact fence is `squatch/thresh.py`, `squatch/providers.py`, `squatch/config.py`, `tests/test_thresh.py`, `tests/test_providers.py`. It owns the new `squatch/thresh.py` and `tests/test_thresh.py` registry paths; its existing provider/config/predecessor-test fence paths are Context, and `tests/test_providers.py` is inside its fence because threshold behavior may contradict it. `phase3-continue-04` depends on `thresh-runtime`, is medium/medium, has expected/stuck budgets of 75m/150m, and fences exactly `tickets` and `tests/test_seeded_phase3_04.py`.

```yaml
ownership:
  thresh-runtime:
    owns:
      - squatch/thresh.py
      - tests/test_thresh.py
    hooks:
      - squatch/providers.py
      - squatch/config.py
      - tests/test_providers.py
```

The finite ordered admissions this continuation carries are:
```yaml
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
Do not implement threshold runtime, dispatch admission, or later Phase 3 work. Do not author a seed beyond `thresh-runtime` and `phase3-continue-04`, change production code, or alter existing tests.

## Scope fence
- tickets
- tests/test_seeded_phase3_03.py

## Acceptance criteria
- `tests/test_seeded_phase3_03.py` proves the emitted set is exactly `thresh-runtime` and `phase3-continue-04`, both lint as confirmed seed tickets citing section 20 alone, with exact edges `rework-stage -> thresh-runtime -> phase3-continue-04` and a batch within `seeding.max_seeds_per_admission`.
- `tests/test_seeded_phase3_03.py` pins `thresh-runtime` at high/high with expected/stuck minutes 120m/180m and `phase3-continue-04` at medium/medium with expected/stuck minutes 75m/150m; each expected value is less than stuck and each stuck value is at or below `drain.max_ticket_minutes`.
- `tests/test_seeded_phase3_03.py` pins the exact `thresh-runtime` fence `squatch/thresh.py`, `squatch/providers.py`, `squatch/config.py`, `tests/test_thresh.py`, `tests/test_providers.py`, its keyed ownership of `squatch/thresh.py` and `tests/test_thresh.py`, and the exact `phase3-continue-04` fence `tickets`, `tests/test_seeded_phase3_04.py`.
- `tests/test_seeded_phase3_03.py` pins `EXISTING_AT_AUTHORING` bytes, proves every existing fence path is in Context, proves `tests/test_providers.py` remains in the `thresh-runtime` fence as predecessor-test closure, and checks each Implement render under `RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM`.
- `tests/test_seeded_phase3_03.py` proves `phase3-continue-04` carries the structured YAML suffix from `dispatch-admission-boundary` through `phase3-exit` in registry order.
- `uv run pytest tests/test_seeded_phase3_03.py -q` exits 0.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_seeded_phase3_03.py -q
uv run pytest -q
```

## Definition of rejected
Stop if the shrinking suffix cannot be represented without duplicating threshold runtime, if its existing predecessor test cannot be fenced, if an emitted ticket cannot fit requisition headroom, or if a required path lies outside this fence.

## Time budget
- expected: 75m
- stuck: 150m
