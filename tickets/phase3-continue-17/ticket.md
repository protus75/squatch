---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- storm-producer-wiring
- storm-notification-activation

## Context
- tests/test_seeded_phase3_11.py
- tests/test_storm.py
- tests/test_box.py
- tests/test_daemon_composition.py

## Plan contract
- section 20

## Goal
Author the production storm dispatch hold and the next shrinking continuation.

## Why
The producer and trip/report activation have merged; the hold now needs one owner for real selection and resume.

## Scope in
Author only confirmed storm-dispatch-hold and phase3-continue-18 plus tests/test_seeded_phase3_17.py. The hold depends on phase3-continue-17 and is KNOWN-DEEP high/high; phase3-continue-18 depends on storm-dispatch-hold and remains medium/medium. Both cite section 20 alone, use 75m/150m budgets and cap 3, and derive fences as owns followed by hooks.

```yaml
ownership:
  storm-dispatch-hold:
    owns:
    - tests/test_storm_hold.py
    hooks:
    - squatch/storm.py
    - squatch/control.py
    - squatch/daemon.py
    - squatch/drain.py
    - squatch/__main__.py
    - tests/test_storm.py
    - tests/test_storm_producer.py
    - tests/test_storm_notification_activation.py
  phase3-continue-18:
    owns:
    - tickets
    - tests/test_seeded_phase3_18.py
    hooks: []
```

The hold is production activation. A drain offer is a whole ticket, so emitting_stage stays diagnostic and is never the selector. Extend newly written occurrence and trip bodies with emitting_origin always present as string or null, validated like emitting_stage; StormLedger.record takes it as an optional argument defaulting to None, and replay treats legacy events lacking it as None. The producer supplies the Box message origin. Suppress only an offered ticket whose stem equals the tripped emitting_origin, before durable dispatch accounting including retry-cap draws. Other stems remain eligible, and a null or non-ticket origin creates no global hold. Trip and occurrence identities remain unchanged. Bind the journal-derived per-stem hold through the live drain's CLI composition root and provide identity-bound resume exactly once through the current-lifecycle control inbox. Journal the decision before mutation; stale lifecycle, pre-trip and wrong-hold releases cannot clear this trip or a later trip. Rehydrate unreleased holds after restart and preserve independently owned manual-pause and merge-admission holds. No later admission activates this hold: this ticket is its production owner before phase3-exit.

The hold's exact embedded Context is `squatch/storm.py`, `squatch/control.py`, `squatch/daemon.py`, `tests/test_storm.py`, `tests/test_storm_producer.py`, `tests/test_storm_notification_activation.py`, `tests/test_daemon_composition.py`, in that order. Only `squatch/drain.py` and `squatch/__main__.py` are fenced on-demand inspection exceptions, read before editing but not embedded. Every other existing fence path is existing Context. The three storm tests are the predecessor migration partition: fence them and migrate dispatch-absence assertions plus exact occurrence/trip body, key-set, and `_event` fixture assertions only as needed to add and validate emitting_origin. Retain occurrence identity, trip-id, report, and every other positive ledger/producer/trip behavior unchanged. `tests/test_daemon_composition.py` is read-only preservation Context and stays unchanged, pinned in the PRESERVATION set and run in Verification.

The producer and notification tests are merged predecessors when the hold is authored, NOT sibling-new. Inspect both then and pin their measured authoring-time sizes alongside the other Context sizes in tests/test_seeded_phase3_17.py. They are excluded only from this continuation's own authoring-time Context because they did not yet exist. Pin the exact future hold Context, production fence, predecessor-test closure, tiers, dependencies, budgets, cap, section 20's historical length, new-path registry owners and every max-effort render under REQ_RENDER_HEADROOM, including the high-tier hold render. Historical sizes must not be compared with later live sizes. Keep delimiter-bearing prompt-spec sources outside Context; phase3-continue-18 must include an established seeded-test pattern that exists at its authoring time, never the sibling-new tests/test_seeded_phase3_17.py.

The finite ordered admissions are:
```yaml
[[storm-dispatch-hold], [checkpoint-push], [daemon-soak], [soak-run], [phase3-exit]]
```
The successor removes only the hold row and carries exact suffix equality, starting at checkpoint-push; do not combine admissions. It authors checkpoint-push and phase3-continue-19 next. Checkpoint-push owns new squatch/checkpoint.py and tests/test_checkpoint.py and hooks squatch/daemon.py, squatch/git.py and tests/test_git.py; its exact Context is squatch/daemon.py, squatch/git.py and tests/test_git.py. Phase3-continue-19 owns tickets and tests/test_seeded_phase3_19.py; its exact Context is tests/test_seeded_phase3_11.py and tests/test_daemon_composition.py. Author no such seeds in this admission.

## Scope out
Do not implement the hold, defer its production activation, author checkpoint work now, combine admissions, or widen the production ownership clarification.

## Scope fence
- tickets
- tests/test_seeded_phase3_17.py

## Acceptance criteria
- `tests/test_seeded_phase3_17.py` pins only the hold and phase3-continue-18 seeds with exact identities, dependencies, high/high versus medium/medium tiers, 75m/150m budgets, cap 3 and owns-then-hooks fences.
- `tests/test_seeded_phase3_17.py` pins the hold's exact Context, every existing fence path as existing Context except squatch/drain.py and squatch/__main__.py, and those two production-root on-demand exceptions alone.
- `tests/test_seeded_phase3_17.py` pins `tests/test_storm.py`, `tests/test_storm_producer.py` and `tests/test_storm_notification_activation.py` as then-existing predecessor migration Context and `tests/test_daemon_composition.py` as unchanged read-only PRESERVATION; it measures both merged producer/notification test sizes at authoring.
- `tests/test_seeded_phase3_17.py` pins authoring-time Context sizes, section 20's historical length, every max-effort render under REQ_RENDER_HEADROOM including the high-tier hold, exact Context and new-path registry owners; no sibling-new or delimiter-bearing prompt-spec file enters Context.
- `tests/test_seeded_phase3_17.py` pins real emitting-origin ticket-stem selection before durable accounting, identity-bound resume and crash recovery in the production root, with unrelated stems eligible, non-ticket origins unable to cause a global hold, and no later activation owner.
- `tests/test_seeded_phase3_17.py` pins exact successor suffix equality after removing only storm-dispatch-hold.

## Verification
```
uv run pytest tests/test_seeded_phase3_17.py -q
uv run pytest -q
```

## Definition of rejected
Reject dormant-only hold construction, absent production-root ownership, another on-demand exception, omitted merged predecessor Context, missing dispatch-absence migration, sibling-new Context, a combined admission, or a render over headroom.

## Time budget
- expected: 75m
- stuck: 150m
