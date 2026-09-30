---
kind: bug
priority: P3
agent_tier: medium
agent_effort: medium
source: box:suggestion
state: draft
---

## Depends on
- none

## Context
- squatch/gates.py
- tests/test_gates.py

## Plan contract
- section 7

## Goal
`run_gates` in `squatch/gates.py` lints every gate in the materialized list before it calls `check` on any of them. If one gate in the list fails `gate_lint`, `run_gates` raises `GateLintError` before any gate's `check` has been awaited, so an earlier autofix-applying gate in the same list never touches the workspace.

## Why
`run_gates` (`squatch/gates.py:180-181`) currently calls `gate_lint(gate)` inside the same loop iteration that calls `gate.check`, one gate at a time. With an autofix gate earlier in the list and a malformed gate later, the autofix gate's `check` runs and mutates the workspace before the later gate's lint fails and raises `GateLintError`, aborting the run. The tree is left partly fixed with no `GateRun` record of the change, which breaks the fail-closed rule: a gate defect is an engine bug and the whole run should refuse before any side effect happens. `gates` is already materialized once (the `Iterable` is consumed into the loop), so a lint pass over the full list ahead of the run pass sees the same sequence the run pass sees. No other part of `run_gates` changes: it still never stops early on a non-lint failure, a crashing gate still fails closed as hard, severity still resolves from config over the shipped default, and `_check` keeps its invariant-5 autofix fixpoint rerun.

## Scope in
- Reorder `run_gates` in `squatch/gates.py` to lint every gate in the materialized list before calling `check` on any of them.
- A regression test in `tests/test_gates.py` with an autofix-applying gate followed by a gate that fails lint, asserting `run_gates` raises `GateLintError` and the autofix gate's `check` was never called.

## Scope out
- `gate_lint`'s own defect checks, `_check`'s autofix fixpoint rerun, severity resolution, and crash-handling in `run_gates` are unchanged.
- `GateReport`, `GateResult`, `GateRun`, and `CoreDrift` are unchanged.
- No engine gate applies an autofix yet (decision-000057), so no other gate implementation is touched.

## Scope fence
- squatch/gates.py
- tests/test_gates.py

## Acceptance criteria
- `run_gates` lints every materialized gate before calling `check` on any of them, so a gate later in the list failing lint raises `GateLintError` before an earlier gate's `check` is ever awaited, checked by `python -m pytest tests/test_gates.py -k lints_every_gate_before_running -q`.
- When a later gate fails lint, an earlier autofix-applying gate's `check` was never called, asserted by `calls == 0` on that earlier gate after `run_gates` raises, checked by `python -m pytest tests/test_gates.py -k lints_every_gate_before_running -q`.
- The existing gate-lint, severity, crash-handling, and autofix-fixpoint behavior of `run_gates` is unchanged, checked by `python -m pytest tests/test_gates.py -q`.

## Verification
```
python -m pytest tests/test_gates.py -k lints_every_gate_before_running -q
python -m pytest tests/test_gates.py -q
```

## Regression
```
python -m pytest tests/test_gates.py -k lints_every_gate_before_running -q
```
- carries: tests/test_gates.py

## Definition of rejected
Stop and throw the branch away if fixing this requires changing `gate_lint`'s defect checks, `_check`'s autofix fixpoint logic, severity resolution, any file outside `squatch/gates.py` and `tests/test_gates.py`, or changes the "run every gate, never stop early" behavior for a non-lint failure.

## Time budget
- expected: 20m
- stuck: 45m
