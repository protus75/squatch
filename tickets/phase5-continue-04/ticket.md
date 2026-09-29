---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- retro-doctor-cli

## Context
- tests/test_seeded_phase5_02.py

## Plan contract
- section 20

## Goal
Author the sole terminal Phase 5 exit admission.

## Why
The manual operator boundary must settle before committed Phase 5 evidence can
author the fixed Phase 6 core.

## Scope in
Author only confirmed `phase5-exit` and new `tests/test_seeded_phase5_04.py`.
Use merged `tests/test_seeded_phase5_02.py` as the continuation pattern; never
embed this admission's `tests/test_seeded_phase5_04.py` or sibling-new
`tests/test_seeded_phase5_03.py` as Context. Carry this complete ordered
registry:
```yaml
- [phase5-exit]
```
`phase5-exit` is KNOWN-HARD high/high, depends transitively on every Phase 5
stem, cites section 20 alone, owns only `tickets`, new
`tests/test_phase5_exit.py`, and new `tests/test_seeded_phase6_core.py`, and
has no successor. Its seeded proof renders the exit and all Phase 6 seeds at
max effort within `RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM`; none cites
or renders section 19.

The authored exit runs on a clean checkout and reads committed evidence only.
It selects the lexicographically latest committed `tickets/retro/[0-9]{6}.md`,
committed by the drain's forced pre-phase-exit hook after the latest Phase 5
feature merge through merged `retro-drain-invoker`; a manual `retro` report is
not accepted. It requires `## Surface scorecard`, numeric spend/tokens, only
existing check surfaces, and a zero escape column. It re-exercises the wired
retro provenance through committed `tests/test_retro_box.py` and passing
`tickets/retro-box-activation/checks.json`, and baseline evidence through
committed `tests/test_baseline.py` and passing
`tickets/baseline-binding-reader/checks.json`: the injected Phase 1 NO-GO
shape is unbound and injected GO followed by spec-major drift is REVOKED. It
proves every named Phase 5 dependency merged, reads no live journal, writes no
report, and never edits engine code.

The exit authors exactly confirmed medium/medium `core-renderer`,
`core-drift-classifier`, and `phase6-continue`, all citing section 20 alone.
`core-renderer` depends on `phase5-exit`; `core-drift-classifier` depends on
`core-renderer`; `phase6-continue` depends on both construction stems. Their
fixed ownership and Context partitions are section 20's registry: renderer
owns new `squatch/hostfiles.py`, new `tests/test_hostfiles.py`, and the core
CLI registration paths; classifier owns the hostfiles module and test; the
continuation owns only `tickets` and new `tests/test_seeded_phase6_01.py`, and
embeds merged `tests/test_seeded_phase5_04.py` rather than sibling-new paths.
It carries the exact remaining rows: `core-drift-activation`, `migrate-config`,
continuation; `host-contract-doc`, `fixture-host-scaffold`, continuation;
`bug-gate-grammar`, `report-inbox-triage`, continuation; `escape-column`,
continuation; KNOWN-DEEP `supervised-merge-hold`, continuation;
`go-grade-machinery`, `go-grade-run`, continuation;
`exit-receipt-machinery`, continuation; ending `phase6-exit` alone with no
successor. No Phase 6 name, owner, dependency, Context path, or exit read is
invented.

## Scope out
Do not implement an exit feature, invent a Phase 6 name, owner, dependency,
Context path, or exit read, use a same-admission or sibling-new seeded Context
fixture, or add a successor after `phase5-exit`.

## Scope fence
- tickets
- tests/test_seeded_phase5_04.py

## Acceptance criteria
- `tests/test_seeded_phase5_04.py` pins `phase5-exit` identity, transitive Phase 5 dependency boundary, section-20-only contract, KNOWN-HARD high/high tier, bounded budget, and exact ownership fence.
- `tests/test_seeded_phase5_04.py` pins the authored `phase5-exit` text for its clean-checkout committed retro, scorecard, provenance, baseline, merged-dependency, no-live-journal, and no-report boundaries, including the forced pre-phase-exit `retro-drain-invoker` producer.
- `tests/test_seeded_phase5_04.py` proves the exact Phase 6 core identities, edges, tiers, section-20-only citations, ownership, Context exclusions, fixed remaining rows, and max-effort render headroom from the authored ticket text.
- `tests/test_seeded_phase5_04.py` proves the merged continuation fixture and excludes both same-admission and sibling-new seeded tests from Context.
- `tests/test_seeded_phase5_04.py` proves the one-row terminal registry and absence of every successor.

## Verification
```
uv run pytest tests/test_seeded_phase5_04.py -q
uv run pytest -q
```

## Definition of rejected
Reject a nonterminal exit, a wrong continuation fixture, an invented Phase 6
boundary, a Context path that does not exist at authoring, or any successor
after `phase5-exit`.

## Time budget
- expected: 75m
- stuck: 150m
