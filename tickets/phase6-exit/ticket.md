---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: high
agent_effort: high
---
## Depends on
- exit-receipt-machinery

## Context
- squatch/artifacts.py
- tickets/go-grade-run/review-baseline-report.json

## Plan contract
- section 20

## Goal
Close Phase 6 from registered fixture-host evidence.

## Why
The registered host-loop machinery must merge before its receipt can close Phase 6.

## Scope in
Run the registered `eval/host_loop.py` `run()` producer and serialize its returned
`HostLoopReport` to fenced `tickets/phase6-exit/host-loop-report.json`. Construct
and serialize the terminal receipt to fenced `tickets/phase6-exit/exit-receipt.json`.
The exit Implement, rather than `run()`, writes both OUTBOX files; validate their
bytes through `KNOWN_ARTIFACTS[HOST_LOOP_REPORT]` and
`KNOWN_ARTIFACTS[EXIT_RECEIPT]` from `squatch.stages`. Those entries are
ordinary-lane validators, not writers the producer calls.
`squatch/artifacts.py` owns the artifact names and schemas; this exit makes no
engine-code edit.

Read the committed `tickets/go-grade-run/review-baseline-report.json` through
`ReviewBaselineReport` and `REVIEW_BASELINE_REPORT`. `go-grade-machinery` owns
that schema and its writer; `go-grade-run` produced the committed file. Resolve
its embedded verdict identity against the latest current-build matching
`review_baseline` journal signal: signal `GO` maps to receipt enum `GO`, and
signal `NO-GO` maps to receipt enum `NO_GO`; an absent or mismatched identity
rejects the exit.

Prove the closed `HostLoopReport` members in schema order: at least three
distinct-run `machine_ticket_merge` entries, then
`report_to_regression_bug_loop`, then `escape_attribution`. Set
`host_loop_digest` to lowercase SHA-256 over the exact schema-validated
host-loop report bytes. Live-host K>=10 and real-host bug-loop evidence are
forbidden exit inputs.

`phase6-exit` is the terminal last-row sole KNOWN-HARD high/high seed, depends
on `exit-receipt-machinery`, and transitively depends on every Phase 6 payload.
It authors no successor and owns/fences only
`tickets/phase6-exit/host-loop-report.json`,
`tickets/phase6-exit/exit-receipt.json`, and new `tests/test_phase6_exit.py`.

`phase6-exit` partition: Embedded Context: `squatch/artifacts.py` and
`tickets/go-grade-run/review-baseline-report.json`; measured on-demand:
`eval/host_loop.py` and `squatch/stages.py`.

## Scope out
Do not edit engine code, read live-host K>=10 or real-host bug-loop evidence,
invent a writer call in the producer, or author a successor.

## Scope fence
- tickets/phase6-exit/host-loop-report.json
- tickets/phase6-exit/exit-receipt.json
- tests/test_phase6_exit.py

## Acceptance criteria
- `tests/test_phase6_exit.py` proves `run()` returns the registered `HostLoopReport`, the exit serializes both fenced OUTBOX files, and their bytes validate through `KNOWN_ARTIFACTS[HOST_LOOP_REPORT]` and `KNOWN_ARTIFACTS[EXIT_RECEIPT]`.
- `tests/test_phase6_exit.py` proves the closed host-loop member order, lowercase SHA-256 digest, committed GO-grade report custody, and matching current-build journal identity mapping of `GO` to `GO` and `NO-GO` to `NO_GO`.
- `tests/test_phase6_exit.py` rejects absent or mismatched verdict identity and forbidden live-host inputs, preserves the terminal fence, and proves no engine-code edit or successor.

## Verification
```
uv run pytest tests/test_phase6_exit.py -q
uv run pytest -q
```

## Definition of rejected
Reject fabricated or unregistered evidence, an invalid OUTBOX artifact, a
missing or mismatched verdict identity, overflow, or a successor.

## Time budget
- expected: 75m
- stuck: 150m
