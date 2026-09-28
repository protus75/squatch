---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- retro-box-activation

## Context
- tests/test_seeded_phase4_05.py

## Plan contract
- section 20

## Goal
Author the first Phase 5 feature and carry the fixed finite Phase 5 suffix.

## Why
The core retro path must merge before scorecard work can treat its module and
tests as existing evidence, while later continuations preserve a bounded queue.

## Scope in
Author only confirmed `scorecard-reporting`, `phase5-continue-02`, and
`tests/test_seeded_phase5_01.py`. Both tickets cite section 20 alone, start
medium/medium, and use expected/stuck budgets within
`drain.max_ticket_minutes`. `scorecard-reporting` depends on
`retro-box-activation`; it owns and fences new `squatch/scorecard.py` and
`tests/test_scorecard.py` plus the then-merged `squatch/retro.py` and
`tests/test_retro.py`. Those two merged retro paths are Context, or are
individually named measured on-demand exceptions if headroom requires. Pin their
authoring-time byte sizes as synthetic render fixtures only and never compare
those fixture values with later live file sizes.

The authored `scorecard-reporting` ticket must state the section-20 projection
contract without inference. It extends `RetroWindow` with the deterministically
ordered `(ticket, code, verdict, bypassed)` observations from well-formed
completed check invoices and adds immutable `SurfaceScorecardRow` and
`Scorecard` models plus pure `project_scorecard(RetroWindow)`. It pins every
field and calculation exactly as section 20 does: distinct evaluated tickets,
non-bypassed failing catches, bypass count, zero Phase 5 escapes, rates, the
25-ticket prune threshold, surface ordering, and boundary/spend/token/signal/
gate-failure summary fields. It requires a deterministic `## Surface scorecard`
report table and forbids projection writes or effects. New
`tests/test_scorecard.py` owns all new assertions, including malformed invoice
exclusion and input immutability; merged `tests/test_retro.py` is
preservation-only and remains byte-for-byte unchanged.

`phase5-continue-02` depends on `scorecard-reporting`, owns only `tickets` and
new `tests/test_seeded_phase5_02.py`, and embeds the already-merged
`tests/test_seeded_phase4_05.py` continuation pattern. The
new-in-this-admission `tests/test_seeded_phase5_01.py` is explicitly excluded
from Context. Only `squatch/scorecard.py`, `tests/test_scorecard.py`, and
`tests/test_seeded_phase5_02.py` are sibling-new and excluded from Context.

Carry this complete finite ordered admission registry:
```yaml
- [scorecard-reporting, phase5-continue-02]
- [status-projection, baseline-binding-reader, phase5-continue-03]
- [retro-doctor-cli, phase5-continue-04]
- [phase5-exit]
```
The second row's `phase5-continue-03` depends on both feature stems. The third
row's `phase5-continue-04` depends on `retro-doctor-cli`. The terminal row is
KNOWN-HARD high/high `phase5-exit` with no successor.

Pin the remaining registry ownership now. `status-projection` owns/fences
existing `squatch/status.py`, new `tests/test_status.py`, and the merged
scorecard and Box seams/tests. `baseline-binding-reader` owns/fences new
`squatch/baseline.py` and `tests/test_baseline.py` plus `squatch/journal.py`,
`squatch/config.py`, and the machine-ticket starting-state caller named by its
requisition. `retro-doctor-cli` owns/fences new `squatch/doctor.py` and
`tests/test_doctor.py` plus `squatch/retro.py`, `squatch/__main__.py`, and their
focused tests. `phase5-exit` owns/fences `tickets`, new
`tests/test_phase5_exit.py`, and new `tests/test_seeded_phase6_core.py`.
Production roots or predecessor suites too large to embed are individually
named measured on-demand exceptions by their future ticket.

Every numbered continuation owns only `tickets` and its matching new
`tests/test_seeded_phase5_<nn>.py`, carries the remaining rows verbatim, and
embeds the immediately preceding merged seeded-test pattern except for the
explicit `phase5-continue-02` fixture rule above. No continuation adds a
successor after `phase5-exit`.

## Scope out
Do not implement a Phase 5 feature, use sibling-new Context, use
`tests/test_seeded_phase5_01.py` as the next continuation pattern, compare
historical fixture sizes to later live files, or change the fixed suffix.

## Scope fence
- tickets
- tests/test_seeded_phase5_01.py

## Acceptance criteria
- `tests/test_seeded_phase5_01.py` pins the exact first-row identities, edges, tiers, budgets, ownership fences, section-20-only contracts, and two-seed admission cap.
- `tests/test_seeded_phase5_01.py` pins the then-merged retro Context or named on-demand partition, synthetic authoring-size fixtures, sibling-new exclusions, and max-effort render headroom.
- The emitted scorecard ticket pins section 20's exact observation tuple, closed model fields, calculations, Phase 5 zero-escape rule, pure read-only projection, deterministic report table, focused test cases, and byte-for-byte preservation of `tests/test_retro.py`.
- `tests/test_seeded_phase5_01.py` pins the already-merged Phase 4 continuation fixture for `phase5-continue-02`, excludes the new Phase 5 seeded test from Context, and carries every later row, dependency, owner, and terminal without a successor.
- `uv run pytest -q` proves the established seeded-test and ticket contracts remain green.

## Verification
```
uv run pytest tests/test_seeded_phase5_01.py -q
uv run pytest -q
```

## Definition of rejected
Reject an off-registry feature, a changed row or edge, sibling-new Context, live
size comparison against a synthetic fixture, the wrong continuation pattern,
more than three seeds, or a successor after `phase5-exit`.

## Time budget
- expected: 75m
- stuck: 150m
