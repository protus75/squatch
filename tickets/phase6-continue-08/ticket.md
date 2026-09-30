---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- exit-receipt-machinery

## Context
- tests/test_seeded_phase6_06.py

## Plan contract
- section 20

## Goal
Author the terminal fixed Phase 6 admission.

## Why
The registered host-loop machinery must merge before its receipt can close Phase 6.

## Scope in
Author confirmed source-seed `phase6-exit` plus new
`tests/test_seeded_phase6_08.py`. Every payload and continuation cites section 20 alone and starts medium/medium unless KNOWN-DEEP or KNOWN-HARD high/high.
Render every authored seed at max effort within
`RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM`; never render section 19,
and preserve section 20's compact-render sentinels. Embed only merged Context;
never embed new or sibling-new paths.

Carry this exact terminal admission:
```yaml
- [phase6-exit]
```

`phase6-exit` depends on `exit-receipt-machinery`, transitively depends on
every Phase 6 payload, and is the last row's sole KNOWN-HARD high/high seed.
It authors no successor and owns/fences only
`tickets/phase6-exit/host-loop-report.json`,
`tickets/phase6-exit/exit-receipt.json`, and new `tests/test_phase6_exit.py`.
It runs the registered `eval/host_loop.py` `run()` producer and reads the
committed GO-grade report at
`tickets/go-grade-run/review-baseline-report.json` through
`ReviewBaselineReport` / `REVIEW_BASELINE_REPORT`. It resolves the report's
embedded verdict identity against the latest current-build matching
`review_baseline` journal signal:
signal `GO` maps to receipt enum `GO`, while
signal `NO-GO` maps to receipt enum `NO_GO`; missing or mismatched signal
identity rejects the exit. It proves the three closed
host-loop members. Its `host_loop_digest` is lowercase SHA-256 over the
exact schema-validated host-loop report bytes. `squatch/artifacts.py` owns the
artifact names and schemas; `squatch/stages.py` `KNOWN_ARTIFACTS` registers
their ordinary-lane writers. It makes no engine-code edit.
Live-host K>=10 and real-host bug-loop evidence are forbidden exit inputs.

`phase6-exit` partition: Embedded Context: none; measured on-demand: none.

The terminal row contains `phase6-exit` alone, has no successor, and authors no
continuation tail.

## Scope out
Do not implement a payload, use sibling-new Context, render section 19, or add
successors.

## Scope fence
- tickets
- tests/test_seeded_phase6_08.py

## Acceptance criteria
- `tests/test_seeded_phase6_08.py` pins the sole terminal row, exact exit fence and Context partition, and no continuation tail.
- `tests/test_seeded_phase6_08.py` proves section-20-only max-effort rendering and the exit's KNOWN-HARD custody.

## Verification
```
uv run pytest tests/test_seeded_phase6_08.py -q
uv run pytest -q
```

## Definition of rejected
Reject changed contracts, unregistered or fabricated evidence, overflow, or
successors.

## Time budget
- expected: 75m
- stuck: 150m
