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
- squatch/retro.py
- tests/test_retro.py

## Plan contract
- section 20

## Goal
Project the completed retro window into a deterministic, read-only surface
scorecard.

## Why
The first Phase 5 derived view needs a closed evidence fold before later status
work can consume scorecard evidence.

## Scope in
Extend `RetroWindow` with `check_observations`: a deterministically ordered
tuple of exactly `(ticket, code, verdict, bypassed)` for every check in each
completed `check/<ticket>/<run>` invoice in the current `Window`. Malformed
completions contribute no observation.

Add immutable `SurfaceScorecardRow(surface, evaluated_tickets, catches,
escapes, bypass_count, catch_rate, escape_rate, prune_candidate)` and
`Scorecard(boundary, merged_ticket_count, spend_usd, tokens, signal_counts,
gate_failure_count, surfaces)` models in `squatch/scorecard.py`. Add pure
`project_scorecard(RetroWindow) -> Scorecard`: `surface` is check code,
`evaluated_tickets` is the number of distinct observed tickets for that code,
`catches` is non-bypassed `verdict: fail` observations, and `bypass_count` is
observations with `bypassed` true. `catch_rate` is catches divided by all
observations for that code, zero when absent. Phase 5 has no bug-report
producer, so `escapes` and `escape_rate` are exactly zero until the Phase 6
escape-column ticket. `prune_candidate` is true only when
`evaluated_tickets >= 25` and both catches and escapes are zero. Sort rows by
surface and carry the RetroWindow boundary, merged-ticket count, spend, tokens,
signal counts, and gate-failure count exactly into `Scorecard`.

The projection performs no filesystem, journal, Git, Box, or provider operation
and writes nothing. `render_report` snapshots scorecard fields into a
deterministic `## Surface scorecard` table.

New `tests/test_scorecard.py` owns all assertions: invoice folding,
malformed-input exclusion, distinct-ticket counting, bypass-versus-catch
semantics, zero-denominator rates, the 25-ticket prune threshold, surface row
ordering, report rendering, and input immutability. `tests/test_retro.py` is
preservation-only regression evidence and remains byte-for-byte unchanged.

`squatch/retro.py` and `tests/test_retro.py` are then-merged Context. Their
authoring-time byte sizes are synthetic render fixtures: 16091 and 20072 bytes,
respectively. Never compare these fixture values with later live file sizes.

## Scope out
Do not write a projection, infer malformed invoices, add a Phase 5 escape
producer, reorder surfaces, or edit `tests/test_retro.py`.

## Scope fence
- squatch/scorecard.py
- tests/test_scorecard.py
- squatch/retro.py
- tests/test_retro.py

## Acceptance criteria
- `tests/test_scorecard.py` proves invoice folding, the exact ordered observation tuple, and malformed-input exclusion for completed check invoices.
- `tests/test_scorecard.py` proves every closed scorecard field and calculation: distinct-ticket counting, bypass-versus-catch semantics, zero-denominator rates, zero Phase 5 escapes, and the 25-ticket prune threshold.
- `tests/test_scorecard.py` proves sorted surface rows, deterministic `## Surface scorecard` report rendering, and that projection leaves its input unchanged while performing no writes or effects.
- `tests/test_retro.py` remains byte-for-byte unchanged and passes as preservation-only regression evidence.

## Verification
```
uv run pytest tests/test_scorecard.py tests/test_retro.py -q
uv run pytest -q
```

## Definition of rejected
Reject a malformed-invoice observation, an inferred escape, a projection effect
or write, a nondeterministic row or report order, or a changed retro suite.

## Time budget
- expected: 75m
- stuck: 150m
