---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: high
agent_effort: high
---
## Depends on
- phase3-continue-17

## Context
- squatch/storm.py
- squatch/control.py
- squatch/daemon.py
- tests/test_storm.py
- tests/test_storm_producer.py
- tests/test_storm_notification_activation.py
- tests/test_daemon_composition.py

## Plan contract
- section 20

## Goal
Activate the journal-derived storm dispatch hold in the live bootstrap drain.

## Why
Trips are now durable and reported; dispatch suppression needs one production owner without turning diagnostic stage data into a selector.

## Scope in
Extend newly written storm occurrence and trip bodies with `emitting_origin`, always present as a string or null and validated like `emitting_stage`. `StormLedger.record` accepts `emitting_origin` as an optional argument defaulting to None; replay reads legacy occurrence and trip events lacking it as None. The producer supplies the Box message origin. Occurrence identity, trip-id, and report behavior remain unchanged.

A drain offer is a whole ticket, so `emitting_stage` stays diagnostic and is never the selector. Select only an offered ticket whose stem equals the tripped `emitting_origin`, suppressing it before retry-cap draws or any other durable dispatch accounting. Other stems remain eligible; null and non-ticket origins create no global hold.

Bind the journal-derived per-stem hold through the live drain's CLI composition root. Journal a hold decision before its mutation. Resume is identity-bound exactly once through the current-lifecycle control inbox: stale lifecycle, pre-trip, and wrong-hold releases cannot clear this trip or a later trip. Rehydrate unreleased storm holds after restart while preserving independently owned manual-pause and merge-admission holds. This ticket is the production owner; no later admission activates the hold before `phase3-exit`.

Migrate the three predecessor storm tests' dispatch-absence assertions and, only as needed for `emitting_origin`, their exact occurrence/trip body, key-set, and `_event` fixture assertions. Retain occurrence identity, trip-id, report, and every other positive ledger, producer, and trip assertion. `tests/test_daemon_composition.py` is read-only preservation Context and remains unchanged. `squatch/drain.py` and `squatch/__main__.py` are fenced on-demand inspection exceptions; every other existing fence path is Context.

## Scope out
Do not alter ticket selection by emitting stage, create a global hold for an unknown origin, defer production activation, or change preservation Context.

## Scope fence
- tests/test_storm_hold.py
- squatch/storm.py
- squatch/control.py
- squatch/daemon.py
- squatch/drain.py
- squatch/__main__.py
- tests/test_storm.py
- tests/test_storm_producer.py
- tests/test_storm_notification_activation.py

## Acceptance criteria
- `tests/test_storm_hold.py` proves nullable durable emitting-origin bodies, legacy replay, and Box-origin propagation without changing occurrence or trip identities.
- `tests/test_storm_hold.py` proves only the matching offered ticket is held before durable accounting, unrelated stems proceed, and null or non-ticket origins do not create a global hold.
- `tests/test_storm_hold.py` proves decision-before-mutation, identity-bound current-lifecycle resume, stale/pre-trip/wrong-hold rejection, crash recovery, and independent manual-pause and merge-admission ownership.
- `tests/test_storm_hold.py` proves the per-stem hold is bound through the live drain's CLI composition root, so a drain assembled through that root suppresses the tripped stem and resumes it.
- The named predecessor tests migrate only the permitted dispatch-absence and emitting-origin body assertions; `tests/test_daemon_composition.py` passes unchanged.

## Verification
```
uv run pytest tests/test_storm_hold.py tests/test_storm.py tests/test_storm_producer.py tests/test_storm_notification_activation.py tests/test_daemon_composition.py -q
uv run pytest -q
```

## Definition of rejected
Reject a stage-selected or global hold, dispatch accounting before suppression, a non-durable decision, a release that can clear another lifecycle or hold, dormant-only construction, or an edit outside the fence.

## Time budget
- expected: 75m
- stuck: 150m
