---
kind: chore
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

## Goal
`tests/test_gates.py` gains two tests of `run_gates` in `squatch/gates.py`. First, a test proves that when a gate whose `check` raises an ordinary exception is followed by a passing gate, `run_gates` still runs the later gate: the crash becomes a hard `run_record`-coded failure and the following gate's pass result is still returned. Second, a test proves that when a gate's `check` raises `asyncio.CancelledError`, `run_gates` lets the cancellation propagate out of the call instead of folding it into a gate-crashed finding. `squatch/gates.py` itself is unchanged.

## Why
The only existing proof that `run_gates` keeps going after a failure uses a gate that returns a fail, not one that crashes, so the `continue` on the crash branch (squatch/gates.py:186-191) is unproven against a trailing gate. Cancellation is untested entirely, and the driver's stuck-budget kill depends on `CancelledError` reaching the caller rather than being swallowed as a routable finding -- a future widening of the `except Exception` handler would silently defeat that kill with nothing to catch it. Two small tests lock in both behaviors at the unit level, cheaply, before either one regresses.

## Scope in
- Add the two tests described above to tests/test_gates.py.

## Scope out
- Any change to squatch/gates.py or any other production module.
- Any change to other test files.

## Scope fence
- tests/test_gates.py

## Acceptance criteria
- A new test `test_a_crashing_gate_does_not_stop_later_gates` in `tests/test_gates.py` runs `run_gates` on the gate list `[Crash(), StubGate(passing())]`, where `Crash` is a gate whose `check` raises a plain `RuntimeError`, and asserts the returned `GateRun.results` has length 2, checked by `pytest tests/test_gates.py::test_a_crashing_gate_does_not_stop_later_gates`.
- The same test asserts the first result is a hard failure with code `run_record` and a message containing `RuntimeError`, checked by `pytest tests/test_gates.py::test_a_crashing_gate_does_not_stop_later_gates`.
- The same test asserts the second result's report has verdict `pass`, checked by `pytest tests/test_gates.py::test_a_crashing_gate_does_not_stop_later_gates`.
- A new test `test_cancelled_error_propagates_through_run_gates` in `tests/test_gates.py` runs `run_gates` on a gate list containing one gate whose `check` raises `asyncio.CancelledError`, and asserts the `run_gates` call itself raises `asyncio.CancelledError`, checked by `pytest tests/test_gates.py::test_cancelled_error_propagates_through_run_gates`.
- `squatch/gates.py` carries no changes, checked by `git diff --stat squatch/gates.py` producing no output.

## Verification
```
pytest tests/test_gates.py::test_a_crashing_gate_does_not_stop_later_gates
pytest tests/test_gates.py::test_cancelled_error_propagates_through_run_gates
pytest tests/test_gates.py
git diff --stat squatch/gates.py
```

## Definition of rejected
If either behavior does not already hold -- a crash actually stops later gates from running, or cancellation actually gets folded into a gate-crashed finding -- stop without changing squatch/gates.py to make the test pass. File the mismatch as a bug via the Suggestion Box; this ticket only pins existing behavior with tests.

## Time budget
- expected: 15m
- stuck: 30m
