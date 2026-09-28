---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- reliability-battery

## Context
- tests/test_seeded_phase4_02.py

## Plan contract
- section 20

## Goal
Author the no-code reliability run and retain the terminal Phase 4 suffix.

## Why
The reliability battery owns the executable evidence boundary; its separate run
must produce the committed report before Phase 4 can be closed.

## Scope in
Author only confirmed `reliability-run` and `phase4-continue-05`, plus
`tests/test_seeded_phase4_04.py`. Use the established seeded Phase 4 pattern and
refine then-existing Context and fences only when they exist. `reliability-run` is
a medium/medium no-code OUTBOX producer: it invokes only the merged public
reliability battery and canonical ordinary-lane writer, leaving
`tickets/reliability-run/reliability-battery-report.json` uncommitted for ordinary
lift. `phase4-continue-05` depends on `reliability-run`, owns only `tickets` and
`tests/test_seeded_phase4_05.py`, and authors the terminal admission.

Both tickets cite section 20 alone, use expected/stuck budgets within
`drain.max_ticket_minutes`, and name only existing Context. Every existing fence
path is existing Context unless an explicitly measured on-demand headroom exception
is named. Preserve predecessor tests and bind invalidated assertions to their
editing owner. Measure Context at authoring time and prove the max-effort render
remains below `RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM`. Sibling-new paths
are never Context. Delimiter exclusion means `specs.DATA_MARKER` is absent from
Context file content; do not substitute a bare-substring check. Keep prompt sources
including `squatch/specs.py` out of Context.

`phase4-exit` is KNOWN-HARD high/high, depends on `reliability-run`, reads only the
committed reliability report before authoring Phase 5 core, and owns the terminal
Phase 4 exit boundary. Do not implement it in this admission.

Carry this complete finite ordered admission registry:
```yaml
[[reliability-run, phase4-continue-05],
 [phase4-exit]]
```
The next continuation removes only the first row and carries the remainder
unchanged. Every nonterminal admission has exactly its payload and next numbered
continuation under the three-seed cap. The terminal admission is `phase4-exit`
alone and has no successor.

## Scope out
Do not implement reliability behavior, run the battery, author beyond
`reliability-run` plus `phase4-continue-05`, or rename, reorder, add, omit, or
split a registry payload.

## Scope fence
- tickets
- tests/test_seeded_phase4_04.py

## Acceptance criteria
- `tests/test_seeded_phase4_04.py` pins exactly the authored identities, dependency edges, section-20-only contracts, tiers, bounded budgets, ownership fences, and new-path owners.
- `tests/test_seeded_phase4_04.py` proves Context closure, predecessor-test preservation, sibling-new exclusion, `specs.DATA_MARKER` absence from Context content, measured authoring-time Context sizes, and max-effort render headroom.
- `tests/test_seeded_phase4_04.py` proves the complete finite ordered suffix, three-seed cap, numbered continuation sequence, removal of only the first row, and terminal `phase4-exit` alone without a successor.

## Verification
```
uv run pytest tests/test_seeded_phase4_04.py -q
uv run pytest -q
```

## Definition of rejected
Reject reliability implementation or execution in this authoring admission, an
off-registry or reordered payload, sibling-new or delimiter-bearing Context, more
than three seeds, or a successor after `phase4-exit`.

## Time budget
- expected: 75m
- stuck: 150m
