---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- journal-roll
- storm-ledger

## Context
- tests/test_seeded_phase3_11.py
- squatch/box.py
- squatch/daemon.py
- squatch/__main__.py
- tests/test_box.py
- tests/test_daemon_composition.py

## Plan contract
- section 20

## Goal
Author storm producer wiring, notification activation, and the next continuation.

## Why
The storm ledger will be an existing dormant boundary when these successors are authored.

## Scope in
Author only confirmed `storm-producer-wiring`, `storm-notification-activation`, and `phase3-continue-17` seeds plus `tests/test_seeded_phase3_16.py`. Producer wiring depends on `phase3-continue-16`; notification activation depends on `storm-producer-wiring`; the successor depends on both. All use medium/medium, 75m/150m budgets, cap 3, cite section 20 alone, and derive fences as owns followed by hooks.

```yaml
ownership:
  storm-producer-wiring:
    owns:
    - tests/test_storm_producer.py
    hooks:
    - squatch/storm.py
    - squatch/box.py
    - squatch/daemon.py
    - tests/test_storm.py
  storm-notification-activation:
    owns:
    - tests/test_storm_notification_activation.py
    hooks:
    - squatch/storm.py
    - squatch/box.py
    - squatch/daemon.py
    - squatch/__main__.py
    - tests/test_storm.py
    - tests/test_storm_producer.py
  phase3-continue-17:
    owns:
    - tickets
    - tests/test_seeded_phase3_17.py
    hooks: []
```

Storm producer wiring uses the then-existing `squatch/storm.py` and `tests/test_storm.py` Context, wiring every box arrival, including a signature-dedup hit, to one stable occurrence identity through the daemon/box seam while production composition remains dormant. `tests/test_storm.py` is its fenced migration target for the ledger dormancy assertion; `tests/test_box.py` and `tests/test_daemon_composition.py` are read-only preservation Context.

Storm notification activation migrates the storm dormancy assertion and activates the section 12 trip signal plus its one P0 `failure_report`. Its real production fence includes `squatch/__main__.py`; daemon-only construction is not activation. The trip identity is deterministic over `(signature, first_live_occurrence_id, crossing_occurrence_id)` and replay cannot mint a second trip. `tests/test_storm.py` and `tests/test_storm_producer.py` are fenced migration targets; `tests/test_box.py` and `tests/test_daemon_composition.py` remain read-only preservation. Dispatch suppression stays exclusively in `storm-dispatch-hold`.

Every existing fence path is existing Context; there are no on-demand exceptions. The only sibling-new paths are `tests/test_storm_producer.py`, `tests/test_storm_notification_activation.py`, and `tests/test_seeded_phase3_17.py`; none may enter sibling Context. Keep delimiter-bearing prompt-spec sources outside Context. Pin authoring-time Context sizes, section 20's historical length, the `PRESERVATION` set, every max-effort render under `REQ_RENDER_HEADROOM`, exact Context, and each new path's registry owner.

The finite ordered admissions are:
```yaml
[[storm-producer-wiring, storm-notification-activation], [storm-dispatch-hold],
 [checkpoint-push], [daemon-soak], [soak-run], [phase3-exit]]
```

## Scope out
Do not implement storm behavior, combine producer and notification activation, add dispatch suppression, or author beyond phase3-continue-17.

## Scope fence
- tickets
- tests/test_seeded_phase3_16.py

## Acceptance criteria
- `tests/test_seeded_phase3_16.py` pins identities, dependencies, tiers, budgets, cap, owns-then-hooks fences, Context, new-path owners, preservation/migration classification, and authoring-time render headroom.
- It treats `squatch/storm.py` and `tests/test_storm.py` as existing Context for the authored storm seeds, fences `squatch/__main__.py` for notification activation, and limits sibling-new paths to the clarification's exact set.
- `tests/test_seeded_phase3_16.py` pins the producer's stable occurrence identity and dormant composition, notification's deterministic replay-safe trip and P0 report, and keeps dispatch hold separate.
- `tests/test_seeded_phase3_16.py` pins exact successor suffix equality after removing only the producer/notification pair.

## Verification
```
uv run pytest tests/test_seeded_phase3_16.py -q
uv run pytest -q
```

## Definition of rejected
Reject a missing existing fence Context, sibling-new Context, on-demand exception, absent production-root fence, combined admission, or render over headroom.

## Time budget
- expected: 75m
- stuck: 150m
