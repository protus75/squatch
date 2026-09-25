---
state: confirmed
source: human
priority: P2
kind: feature
---
# Add a per-call max_delay override to compute_delay

## Depends on
- none

## Context
- src/queuelet/backoff.py

## Goal / Why
Tests exercising Worker retries sleep up to 30s with no way to cap the
delay per call; add an override so callers can bound it.

## Scope in / Scope out
In: an optional `max_delay` param on `compute_delay`, defaulting to
`MAX_DELAY` so current callers are unaffected.
Out: serialize.py and every other module are unchanged -- backoff-only.

## Scope fence
- src/queuelet/backoff.py
- tests/test_backoff.py

## Acceptance criteria
- `compute_delay(attempt)` with no second arg is unchanged (defaults
  to `MAX_DELAY`).
- `compute_delay(attempt, max_delay=X)` never returns more than `X`.
- `compute_delay(0, max_delay=...)` still raises `ValueError`.
- All existing tests in tests/test_backoff.py keep passing, plus new
  coverage for the override.

## Verification
- `pytest tests/test_backoff.py`

## Definition of rejected
Throw away if capping needs anything outside backoff.py, or if the
no-argument default behavior changes.

## Time budget
expected 20m, stuck 60m
