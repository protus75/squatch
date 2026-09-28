---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- watchdog-activation

## Context
- tests/test_seeded_phase3_11.py

## Plan contract
- section 20

## Goal
Author provider-cooldown-failover and preserve the remaining finite Phase 4 suffix.

## Why
Bounded admissions must carry the registry unchanged after the watchdog activation.

## Scope in
Author only confirmed `provider-cooldown-failover` and `phase4-continue-03`, plus
tests/test_seeded_phase4_02.py. Use the established Context pattern and inspect the
then-existing tests/test_seeded_phase4_01.py after it has merged; it is not embedded
Context in this admission because this admission creates it.

provider-cooldown-failover depends on watchdog-activation and starts KNOWN-DEEP
high/high. phase4-continue-03 depends on provider-cooldown-failover and starts
medium/medium. Both cite section 20 alone, use expected/stuck budgets within
 drain.max_ticket_minutes, and name only existing Context. Refine the then-existing
Context and exact fences, preserving the following nonempty ownership contract:
```yaml
ownership:
  provider-cooldown-failover:
    owns: [tests/test_provider_cooldown_failover.py]
    hooks: [squatch/providers.py, squatch/timers.py, tests/test_providers.py, tests/test_restart_timers.py, squatch/drain.py, squatch/serve.py, squatch/__main__.py]
  phase4-continue-03:
    owns: [tickets, tests/test_seeded_phase4_03.py]
    hooks: []
```
Provider construction and activation are one registry payload. Author concrete
criteria over classified CLI failures, journaled cooldown Timer arm/fire and restart,
ordered candidate failover using a multi-candidate fixture, and drain/serve wiring.
Keep the live configured provider set unchanged. Preserve single-candidate behavior:
quota exhaustion arms the cooldown and parks without inventing a candidate; the
journal records timer_fired when the window resets. Fixture served-identity evidence
proves failover. Do not implement behavior in this authoring ticket.

Every existing fence path is existing Context unless its measured on-demand
headroom exception is explicitly named. Preserve predecessor tests and bind any
invalidated assertions to their editing owner. Measure Context at authoring time,
exclude all delimiter-bearing prompt sources including squatch/specs.py, and prove
the max-effort render is below RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM.
Sibling-new paths are never Context. The continuation embeds an established seeded
pattern and pins the next registry owners: reliability-battery owns fault injection
and the closed report schema/writer; reliability-run is its no-code OUTBOX producer;
phase4-exit is KNOWN-HARD high/high, transitively follows both, and reads only the
committed report before authoring Phase 5 core. Refine paths only when they exist;
never invent another registry payload or split provider-cooldown-failover.

Carry this complete finite ordered admission registry:
```yaml
[[provider-cooldown-failover, phase4-continue-03],
 [reliability-battery, phase4-continue-04],
 [reliability-run, phase4-continue-05],
 [phase4-exit]]
```
The next continuation removes only the first row and carries the remainder unchanged.
Every nonterminal admission has exactly its payload and next numbered continuation,
at most three seeds. The terminal admission is phase4-exit alone, with no successor.

## Scope out
Do not implement provider cooldown/failover behavior or reliability machinery.
Do not author beyond provider-cooldown-failover plus phase4-continue-03, or rename,
reorder, add, omit, or split a registry payload.

## Scope fence
- tickets
- tests/test_seeded_phase4_02.py

## Acceptance criteria
- `tests/test_seeded_phase4_02.py` pins exactly the two authored identities, dependency edges, section-20-only contracts, high/high provider tier, medium/medium continuation tier, bounded budgets, and the ownership fences.
- `tests/test_seeded_phase4_02.py` proves every existing fence path is existing Context or an explicitly measured on-demand exception, predecessor-test closure, new-path ownership, sibling-new and delimiter-bearing Context exclusion, authoring-time Context sizes, and max-effort render below REQ_RENDER_HEADROOM.
- `tests/test_seeded_phase4_02.py` proves the complete finite ordered suffix, three-seed cap, numbered continuation sequence, removal of only the first row, and terminal phase4-exit-only admission without a successor.

## Verification
```
uv run pytest tests/test_seeded_phase4_02.py -q
uv run pytest -q
```

## Definition of rejected
Reject implementation in this authoring admission, any off-registry or reordered payload, sibling-new or delimiter-bearing Context, more than three seeds, or a successor after phase4-exit.

## Time budget
- expected: 75m
- stuck: 150m
