---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- provider-cooldown-failover

## Context
- tests/test_seeded_phase4_01.py

## Plan contract
- section 20

## Goal
Author the reliability payload and retain the finite Phase 4 suffix.

## Why
The bounded provider admission is complete; the remaining registry must be carried
unchanged until the terminal phase exit.

## Scope in
Author only confirmed `reliability-battery`, `phase4-continue-04`, and
`tests/test_seeded_phase4_03.py`. Use the established seeded Phase 4 pattern and
refine then-existing Context and fences only when they exist. The battery owns fault
injection and the closed report schema/writer; `reliability-run` is its no-code
OUTBOX producer. `phase4-exit` is KNOWN-HARD high/high, transitively depends on both
reliability tickets, and reads only the committed report before authoring Phase 5
core.

Every authored ticket cites section 20 alone, uses an expected/stuck budget within
`drain.max_ticket_minutes`, and names only existing Context. Every existing fence
path is existing Context unless an explicitly measured on-demand headroom exception
is named. Preserve predecessor tests and bind invalidated assertions to their editing
owner. Measure Context at authoring time and prove the max-effort render remains
below `RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM`. Sibling-new paths are never
Context. Delimiter exclusion means `specs.DATA_MARKER` is absent from Context file
content; do not substitute a bare-substring check. Keep prompt sources including
`squatch/specs.py` out of Context.

Carry this complete finite ordered admission registry:
```yaml
[[reliability-battery, phase4-continue-04],
 [reliability-run, phase4-continue-05],
 [phase4-exit]]
```
The next continuation removes only the first row and carries the remainder
unchanged. Every nonterminal admission has exactly its payload and next numbered
continuation under the three-seed cap. The terminal admission is `phase4-exit`
alone and has no successor.

## Scope out
Do not implement reliability behavior or author beyond `reliability-battery` plus
`phase4-continue-04`; do not rename, reorder, add, omit, or split a registry payload.

## Scope fence
- tickets
- tests/test_seeded_phase4_03.py

## Acceptance criteria
- `tests/test_seeded_phase4_03.py` pins exactly the authored identities, dependency edges, section-20-only contracts, tiers, bounded budgets, ownership fences, and new-path owners.
- `tests/test_seeded_phase4_03.py` proves Context closure, predecessor-test preservation, sibling-new exclusion, `specs.DATA_MARKER` absence from Context content, measured authoring-time Context sizes, and max-effort render headroom.
- `tests/test_seeded_phase4_03.py` proves the complete finite ordered suffix, three-seed cap, numbered continuation sequence, removal of only the first row, and terminal `phase4-exit` alone without a successor.

## Verification
```
uv run pytest tests/test_seeded_phase4_03.py -q
uv run pytest -q
```

## Definition of rejected
Reject reliability implementation in this authoring admission, an off-registry or
reordered payload, sibling-new or delimiter-bearing Context, more than three seeds,
or a successor after `phase4-exit`.

## Time budget
- expected: 75m
- stuck: 150m
