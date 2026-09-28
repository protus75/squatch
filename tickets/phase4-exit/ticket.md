---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: high
agent_effort: high
---
## Depends on
- reliability-run

## Context
- tickets/reliability-run/reliability-battery-report.json
- squatch/artifacts.py
- eval/reliability_battery.py
- tests/test_reliability_battery.py
- tests/test_seeded_phase4_02.py

## Plan contract
- section 20

## Goal
Close Phase 4 from its committed reliability evidence and author the fixed Phase
5 core.

## Why
The reliability run is the final execution-evidence producer; the exit admits
the bounded next-phase core only after that committed evidence is green.

## Scope in
Read only the committed `tickets/reliability-run/reliability-battery-report.json`
through `squatch.artifacts.ReliabilityBatteryReport` before authoring the Phase 5
core. Its exact, complete member order is
`classified_quota_exhaustion`, `all_candidates_cooling_recovery`, and
`unclassified_failure_preservation`; every member must be green. This is the sole
Phase 4 execution evidence. The prior watchdog obligations are proved by their
merged, transitive predecessors and are not report members or exit reads.

Author exactly confirmed `retro-drain-invoker`, `retro-box-activation`, and
`phase5-continue`, plus `tests/test_phase4_exit.py` and
`tests/test_seeded_phase5_core.py`. Both tickets cite section 20 alone and use
expected/stuck budgets within `drain.max_ticket_minutes`. `retro-drain-invoker`
depends on `phase4-exit`, is KNOWN-DEEP high/high, owns/fences new
`squatch/retro.py`, `specs/retro.md`, and `tests/test_retro.py`, plus existing
`squatch/drain.py`, `squatch/driver.py`, `squatch/artifacts.py`,
`squatch/stages.py`, `tests/test_drain.py`, `tests/test_driver.py`, and
`tests/test_stages.py`; its Context is `squatch/driver.py`,
`squatch/artifacts.py`, and `tests/test_seeded_phase4_02.py`, with drain/stages
modules and their tests measured on-demand exceptions. `retro-box-activation`
depends on `retro-drain-invoker`, is KNOWN-DEEP high/high, owns/fences
predecessor-new `squatch/retro.py`, existing `squatch/box.py`,
`squatch/merge.py`, `tests/test_box.py`, and `tests/test_merge.py`, plus new
`tests/test_retro_box.py`; its Context is `squatch/box.py`,
`tests/test_box.py`, and `tests/test_seeded_phase4_02.py`, with merge code/tests
measured on demand and predecessor-new paths excluded from authoring-time Context.
`phase5-continue` depends on `retro-box-activation`, is medium/medium, owns only
`tickets` plus new `tests/test_seeded_phase5_01.py`, and embeds
`tests/test_seeded_phase4_05.py`; sibling-new core paths are never Context.
This regenerated revision follows the successful `phase4-continue-05` merge;
that embedded predecessor Context now exists on main and must be preserved.

Carry this complete finite ordered admission registry:
```yaml
[[retro-drain-invoker, retro-box-activation, phase5-continue]]
```
The Phase 5 suffix is fixed: `phase5-continue` authors `scorecard-reporting`
plus `phase5-continue-02`; `phase5-continue-02` depends on
`scorecard-reporting` and authors `status-projection`, `baseline-binding-reader`,
plus `phase5-continue-03`; `phase5-continue-03` depends on both feature stems and
authors `retro-doctor-cli` plus `phase5-continue-04`; `phase5-continue-04`
depends on `retro-doctor-cli` and authors only `phase5-exit`, with no successor.

## Scope out
Do not implement or rerun the reliability battery, alter the committed report,
or rename, reorder, add, omit, combine, or split the Phase 5 core or suffix.

## Scope fence
- tickets
- tests/test_phase4_exit.py
- tests/test_seeded_phase5_core.py

## Acceptance criteria
- `tests/test_phase4_exit.py` proves the committed report parses as `ReliabilityBatteryReport`, has the closed three-member order, and every member is green before Phase 5 core authoring.
- `tests/test_seeded_phase5_core.py` pins the exact three core identities, edges, tiers, budgets, fences, Context partitions, predecessor-new and sibling-new exclusions, measured authoring-time sizes, bounded render, and fixed finite Phase 5 suffix.

## Verification
```
uv run pytest tests/test_phase4_exit.py tests/test_seeded_phase5_core.py -q
uv run pytest -q
```

## Definition of rejected
Reject an uncommitted or non-green report, an obsolete report name or member, an
off-registry Phase 5 payload, sibling-new Context, or a successor after
`phase5-exit`.

## Time budget
- expected: 75m
- stuck: 150m
