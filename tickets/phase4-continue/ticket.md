---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- watchdog-event-stream
- notify-transport

## Context
- tests/test_seeded_phase3_11.py

## Plan contract
- section 20

## Goal
Author the first Phase 4 payload batch and preserve the exact finite Phase 4
continuation.

## Why
The phase boundary names the whole suffix once; numbered continuations carry
that authority forward in bounded admissions without letting later authors
invent or reorder payloads.

## Scope in
Author only confirmed `watchdog-detector`, `watchdog-activation`, and
`phase4-continue-02`, plus `tests/test_seeded_phase4_01.py`. Refine their
then-existing Context and exact fences from section 20 without adding a payload.
`watchdog-detector` depends on both `watchdog-event-stream` and
`notify-transport`; `watchdog-activation` depends on `watchdog-detector`; the
next continuation depends on `watchdog-activation`. Detector construction
precedes activation, and activation owns migration of every named predecessor
dormancy test.

Every authored ticket cites section 20 alone, starts at the registry tier,
uses a budget within `drain.max_ticket_minutes`, names only existing Context,
and keeps sibling-new paths out of Context. The seeded test pins exact
identities, edges, ownership, Context closure, predecessor dormancy migration,
new-path owners, the admission cap, authoring-time Context sizes, exclusion of
delimiter-bearing prompt sources including `squatch/specs.py`, and max-effort
render headroom.

Carry this complete finite ordered admission registry:
```yaml
[[watchdog-detector, watchdog-activation, phase4-continue-02],
 [provider-cooldown-failover, phase4-continue-03],
 [reliability-battery, phase4-continue-04],
 [reliability-run, phase4-continue-05],
 [phase4-exit]]
```
Each nonterminal row contains its named payload batch and exactly its next
numbered continuation under the three-seed cap. The next continuation removes
only the first row and carries the remainder unchanged. The terminal admission contains only `phase4-exit`
and has no successor.

## Scope out
Do not implement watchdog behavior, provider failover, or reliability
machinery. Do not author beyond the first payload batch and its one continuation,
or rename, reorder, add, omit, or split a registry payload.

## Scope fence
- tickets
- tests/test_seeded_phase4_01.py

## Acceptance criteria
- `tests/test_seeded_phase4_01.py` proves the exact three authored identities, their dependency edges, registry tiers and bounded budgets, section-20-only contracts, closed fences, Context closure, and new-path ownership.
- `tests/test_seeded_phase4_01.py` proves detector-before-activation ordering, predecessor dormancy-test migration, the three-seed admission cap, and that `phase4-continue-02` removes only the admitted first row.
- `tests/test_seeded_phase4_01.py` proves the complete finite ordered suffix, numbered continuation sequence, terminal `phase4-exit`-only admission, delimiter-bearing Context exclusion, and max-effort render headroom.

## Verification
```
uv run pytest tests/test_seeded_phase4_01.py -q
uv run pytest -q
```

## Definition of rejected
Reject a payload outside the registry, a reordered or missing payload, more
than three seeds in one admission, a sibling-new or delimiter-bearing Context,
activation before detector construction, or a successor after `phase4-exit`.

## Time budget
- expected: 75m
- stuck: 150m
