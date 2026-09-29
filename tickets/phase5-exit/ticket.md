---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: high
agent_effort: high
---
## Depends on
- phase5-continue-04

## Context
- tests/test_retro_box.py
- tests/test_baseline.py
- tests/test_seeded_phase5_03.py

## Plan contract
- section 20

## Goal
Admit the fixed Phase 6 core from committed Phase 5 evidence.

## Why
Phase 6 construction may start only after the terminal Phase 5 operator and
evidence boundary has been mechanically established.

## Scope in
Run this terminal admission on a clean checkout and read committed evidence
only. Select the lexicographically latest committed `tickets/retro/[0-9]{6}.md`.
It must have been committed by the drain's forced pre-phase-exit hook after the
latest Phase 5 feature merge through merged `retro-drain-invoker`; a manual
`retro` report is not accepted. Require `## Surface scorecard`, numeric
spend/tokens, only existing check surfaces, and a zero escape column.

Re-exercise wired retro provenance through committed `tests/test_retro_box.py`
and passing `tickets/retro-box-activation/checks.json`. Re-exercise baseline
evidence through committed `tests/test_baseline.py` and passing
`tickets/baseline-binding-reader/checks.json`: the injected Phase 1 NO-GO shape
is unbound and injected GO followed by spec-major drift is REVOKED. Prove every
named Phase 5 dependency merged, read no live journal, write no report, and
never edit engine code.

Author exactly confirmed medium/medium `core-renderer`, `core-drift-classifier`,
and `phase6-continue`, all citing section 20 alone. `core-renderer` depends on
`phase5-exit`; `core-drift-classifier` depends on `core-renderer`; and
`phase6-continue` depends on both construction stems. Renderer owns new
`squatch/hostfiles.py`, new `tests/test_hostfiles.py`, and core CLI registration
paths `squatch/__main__.py`, `tests/test_cli.py`, and `tests/test_verbs.py`.
Classifier owns `squatch/hostfiles.py` and `tests/test_hostfiles.py`.
`phase6-continue` owns only `tickets` and new `tests/test_seeded_phase6_01.py`,
and embeds merged `tests/test_seeded_phase5_04.py`, never same-admission
`tests/test_seeded_phase6_core.py` or sibling-new `squatch/hostfiles.py` and
`tests/test_hostfiles.py` paths.

Carry these exact remaining rows: `core-drift-activation`, `migrate-config`,
continuation; `host-contract-doc`, `fixture-host-scaffold`, continuation;
`bug-gate-grammar`, `report-inbox-triage`, continuation; `escape-column`,
continuation; KNOWN-DEEP `supervised-merge-hold`, continuation;
`go-grade-machinery`, `go-grade-run`, continuation;
`exit-receipt-machinery`, continuation; ending `phase6-exit` alone with no
successor. No Phase 6 name, owner, dependency, Context path, or exit read is
invented. The seeded proof renders this exit and all Phase 6 seeds at max effort
within `RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM`; none cites or renders
section 19.

Delete any prior uncommitted `core-renderer`, `core-drift-classifier`, or
`phase6-continue` output before authoring the batch. The regenerated
`phase6-continue` and its seeded proof must copy section 20's complete Phase 6
remaining-row contracts: every direct edge through `phase6-continue-08`, exact
owner/fence and Context/on-demand partition, behavior boundary, shrinking
suffix, and terminal `phase6-exit` custody. Naming a row without those fixed
contracts is rejected.

## Scope out
Do not implement an exit feature, read a live journal, accept a manual report,
write a report, edit engine code, invent a Phase 6 boundary, or add a successor
after `phase5-exit`.

## Scope fence
- tickets
- tests/test_phase5_exit.py
- tests/test_seeded_phase6_core.py

## Acceptance criteria
- `tests/test_phase5_exit.py` proves the clean-checkout committed retro selection, scorecard and zero-escape requirements, committed provenance and baseline evidence, merged Phase 5 dependencies, and no-live-journal/no-report boundaries.
- `tests/test_phase5_exit.py` proves the forced pre-phase-exit `retro-drain-invoker` producer and rejects a manual `retro` report.
- `tests/test_seeded_phase6_core.py` pins the exact Phase 6 core identities, edges, tiers, section-20-only citations, ownership, Context partitions, remaining rows, and max-effort render headroom.
- `tests/test_seeded_phase6_core.py` proves `phase6-continue` embeds merged `tests/test_seeded_phase5_04.py` and excludes same-admission and sibling-new paths.
- `tests/test_seeded_phase6_core.py` proves `phase6-continue` carries every section 20 remaining-row direct edge, exact owner/fence, Context/on-demand partition, behavior contract, continuation tail through `phase6-continue-08`, and terminal `phase6-exit` custody without invention.

## Verification
```
uv run pytest tests/test_phase5_exit.py tests/test_seeded_phase6_core.py -q
uv run pytest -q
```

## Definition of rejected
Reject an uncommitted or manual retrospective, a nonzero or invented scorecard
surface, missing committed evidence, an invented Phase 6 boundary, or a
successor after this terminal exit.

## Time budget
- expected: 75m
- stuck: 150m
