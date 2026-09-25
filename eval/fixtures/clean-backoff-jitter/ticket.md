---
state: confirmed
source: human
priority: P2
kind: feature
---
# Add optional jitter to backoff delay

## Depends on
- none

## Context
- src/queuelet/backoff.py

## Goal / Why
Many workers hitting a transient failure at once back off for exactly
the same delay and retry in lockstep; jitter spreads retries out.

## Scope in / Scope out
In: an optional `jitter` parameter on `compute_delay`, in `[0, 1]`,
randomizing the delay by up to that fraction, capped at `MAX_DELAY`.
Out: default (no-jitter) delay values are unchanged; `Worker` and how
it calls `compute_delay` are untouched.

## Scope fence
- src/queuelet/backoff.py
- tests/test_backoff.py

## Acceptance criteria
- `compute_delay(attempt)` with no `jitter` arg is unchanged (jitter
  defaults to 0.0, no randomization).
- `compute_delay(attempt, jitter=X)` for `X > 0` never exceeds
  `MAX_DELAY` and is never negative.
- `compute_delay(0, jitter=...)` still raises `ValueError`.
- Existing tests in tests/test_backoff.py keep passing, plus new
  coverage for jitter's bounds via a deterministic `random.uniform`.

## Verification
- `pytest tests/test_backoff.py`

## Definition of rejected
Throw away if jitter can push the delay above `MAX_DELAY` or below zero.

## Time budget
expected 20m, stuck 60m
