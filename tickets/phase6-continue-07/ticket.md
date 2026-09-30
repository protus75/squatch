---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- go-grade-machinery
- go-grade-run

## Context
- tests/test_seeded_phase6_05.py

## Plan contract
- section 20

## Goal
Author the seventh fixed Phase 6 admission and preserve terminal custody.

## Why
The GO-grade report must merge before host-loop receipt machinery is authored.

## Scope in
Author confirmed source-seed `exit-receipt-machinery` and `phase6-continue-08`,
plus new `tests/test_seeded_phase6_07.py`. Every payload and continuation cites
section 20 alone and starts medium/medium unless KNOWN-DEEP or KNOWN-HARD high/high.
Render every authored seed at max effort within
`RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM`; never render section 19,
and preserve section 20's compact-render sentinels. Embed only the merged
Context partition; never embed new or sibling-new paths.

Carry this exact shrinking suffix:
```yaml
- [exit-receipt-machinery, phase6-continue-08]
- [phase6-exit]
```

`exit-receipt-machinery` depends on `go-grade-run` and owns/fences `squatch/artifacts.py`, `squatch/stages.py`, new `eval/host_loop.py`, new `tests/test_host_loop.py`, `tests/test_gates.py`, and `tests/test_stages.py`. It registers closed writers for `host-loop-report.json` and `exit-receipt.json`; its harness launches supervised `serve` against `hosts/fixture/`, drives machine-actor confirms through the control inbox, records per-member `(member, driven scenario, observable, producing run)` evidence for at least three machine-ticket merges, report-to-regression bug loop, and escape attribution, and never produces terminal artifacts during its build.

`exit-receipt-machinery` partition: Embedded Context: `squatch/artifacts.py`,
`tests/test_gates.py`; measured on-demand: `squatch/stages.py`,
`tests/test_stages.py`, `hosts/fixture/`.

`phase6-exit` depends on `exit-receipt-machinery`, transitively depends on every Phase 6 payload, and is last row's sole KNOWN-HARD high/high seed. It authors no successor and owns/fences only `tickets/phase6-exit/host-loop-report.json`, `tickets/phase6-exit/exit-receipt.json`, and new `tests/test_phase6_exit.py`. It reads GO-grade verdict, accepts GO or NO-GO, proves three members, writes receipt digest, makes no engine-code edit; live-host K>=10 and real-host bug-loop evidence are forbidden exit inputs.

It runs the registered host-loop producer and reads the committed GO-grade report
and its embedded verdict identity; the three closed host-loop members supply
the execution evidence for the receipt.

`phase6-exit` partition: Embedded Context: none; measured on-demand: none.

`phase6-continue-08` depends on `exit-receipt-machinery`. Owns `tickets`, `tests/test_seeded_phase6_08.py`; Context: `tests/test_seeded_phase6_06.py`.

The terminal row contains `phase6-exit` alone, has no successor, and authors no
continuation tail.

## Scope out
Do not implement a payload, use sibling-new Context, render section 19, or add successors.

## Scope fence
- tickets
- tests/test_seeded_phase6_07.py

## Acceptance criteria
- `tests/test_seeded_phase6_07.py` pins row 7, exact remaining fences and Context partitions, and terminal custody.
- `tests/test_seeded_phase6_07.py` proves section-20-only max-effort renders and the sole terminal row with no continuation tail.

## Verification
```
uv run pytest tests/test_seeded_phase6_07.py -q
uv run pytest -q
```

## Definition of rejected
Reject changed contracts, unregistered or fabricated evidence, overflow, or successors.

## Time budget
- expected: 75m
- stuck: 150m
