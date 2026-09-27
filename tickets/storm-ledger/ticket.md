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

## Context
- squatch/journal.py
- tests/test_journal.py

## Plan contract
- section 20

## Goal
Build the dormant storm occurrence ledger.

## Why
The rolled journal supplies the complete stream for a storm window fold.

## Scope in
Add `squatch/storm.py` and `tests/test_storm.py` for section 20's dormant occurrence window. A caller supplies normalized `signature`, replay-stable unique `occurrence_id`, and optional `emitting_stage`. Recording appends one `signal` keyed `storm-occurrence/<signature>/<occurrence_id>` with body `{kind: storm_occurrence, signature, occurrence_id, emitting_stage}`; an identical existing key is idempotent and appends no event. Fold the complete ordered journal across active and immutable rolled segments, retaining timestamps in `(now - T, now]`, grouped by signature. Return ordered live occurrence identities, count, and strict `count > K`, with `K=5`, `T=1 hour`, and expiry at the lower boundary.

`tests/test_storm.py` directly proves the exact key/body, replay idempotence, strict threshold, lower-boundary expiry, and a cross-segment fold. Prove dormancy with an AST transitive `squatch.*` import-closure rooted at `squatch/__main__.py`: `squatch.storm` is not production-reachable. Emit no trip signal, box message, notification, producer wiring, or dispatch hold. `tests/test_journal.py` is read-only preservation and must be verified unchanged.

## Scope out
Do not wire a producer, activate notifications, create a trip, send a box message, or hold dispatch.

## Scope fence
- squatch/storm.py
- tests/test_storm.py

## Acceptance criteria
- `tests/test_storm.py` proves the exact occurrence identity, signal key/body, idempotence, window fold, strict threshold, and lower-boundary expiry.
- `tests/test_storm.py` proves the fold spans a rolled-segment boundary and its AST production import closure proves dormancy.
- `tests/test_storm.py` emits no producer wiring, notification activation, trip, box message, or dispatch hold; `tests/test_journal.py` passes unchanged preservation.

## Verification
```
uv run pytest tests/test_storm.py -q
uv run pytest tests/test_journal.py -q
uv run pytest -q
```

## Definition of rejected
Reject a production-reachable storm import, a non-idempotent replay, or any trip, notification, box, producer, or hold behavior.

## Time budget
- expected: 75m
- stuck: 150m
