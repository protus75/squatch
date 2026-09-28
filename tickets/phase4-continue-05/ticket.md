---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- reliability-run

## Context
- tests/test_seeded_phase4_03.py

## Plan contract
- section 20

## Goal
Author the terminal Phase 4 exit admission.

## Why
The reliability run produces the committed evidence boundary, so its successor
can retain the final exit admission without adding another continuation.

## Scope in
Author only confirmed `phase4-exit` plus `tests/test_seeded_phase4_05.py`.
Use the established seeded Phase 4 pattern. `phase4-exit` is KNOWN-HARD
high/high, depends on `reliability-run`, reads only the committed
`tickets/reliability-run/reliability-battery-report.json` before authoring Phase
5 core, and owns the terminal Phase 4 exit boundary. Its exact Context is
`squatch/artifacts.py`, `eval/reliability_battery.py`,
`tests/test_reliability_battery.py`, and `tests/test_seeded_phase4_02.py`;
the report is sibling-new and is not Context. Its fence is `tickets`, new
`tests/test_phase4_exit.py`, and new `tests/test_seeded_phase5_core.py`; those
two new paths belong to `phase4-exit`, while
`tests/test_seeded_phase4_05.py` belongs only to this continuation.

Both tickets cite section 20 alone, use expected/stuck budgets within
`drain.max_ticket_minutes`, and name only existing Context. Every existing fence
path is existing Context unless an explicitly measured on-demand headroom
exception is named. Preserve predecessor tests and bind invalidated assertions to
their editing owner. Measure Context at authoring time and prove the max-effort
render remains below `RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM`.
Sibling-new paths are never Context. Delimiter exclusion means `specs.DATA_MARKER`
is absent from Context file content; do not substitute a bare-substring check.
Keep prompt sources including `squatch/specs.py` out of Context.

Carry this complete finite ordered admission registry:
```yaml
[[phase4-exit]]
```
The prior continuation removes only its first row and carries this terminal row
unchanged. The terminal admission is `phase4-exit` alone and has no successor.

## Scope out
Do not implement reliability behavior, run the battery, author beyond
`phase4-exit`, or rename, reorder, add, omit, or split a registry payload.

## Scope fence
- tickets
- tests/test_seeded_phase4_05.py

## Acceptance criteria
- `tests/test_seeded_phase4_05.py` pins the terminal admission's identity, dependency edge, section-20-only contract, high/high tier, bounded budget, ownership fence, new-path owners, and committed-report-only input.
- `tests/test_seeded_phase4_05.py` proves Context closure, predecessor-test preservation, sibling-new exclusion, `specs.DATA_MARKER` absence from Context content, measured authoring-time Context sizes, and max-effort render headroom.
- `tests/test_seeded_phase4_05.py` proves the complete finite ordered terminal suffix, three-seed cap, removal of only the first row, and `phase4-exit` alone without a successor.

## Verification
```
uv run pytest tests/test_seeded_phase4_05.py -q
uv run pytest -q
```

## Definition of rejected
Reject reliability implementation or execution in this authoring admission, an
off-registry or reordered payload, sibling-new or delimiter-bearing Context, more
than three seeds, or a successor after `phase4-exit`.

## Time budget
- expected: 75m
- stuck: 150m
