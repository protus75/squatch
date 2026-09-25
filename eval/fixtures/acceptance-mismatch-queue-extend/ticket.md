---
state: confirmed
source: human
priority: P2
kind: feature
---
# Add Queue.extend() for bulk enqueueing

## Depends on
- none

## Context
- src/queuelet/queue.py
- tests/test_queue.py

## Goal / Why
Callers loading a batch of jobs at startup call `put()` in a loop; add
`extend()`, preserving `put()`'s same-priority FIFO tie-break order.

## Scope in / Scope out
In: `Queue.extend(jobs, priority=0)`, enqueuing each job in order.
Out: `Queue.get()`/`Queue.put()`'s single-job behavior does not change.

## Scope fence
- src/queuelet/queue.py
- tests/test_queue.py

## Acceptance criteria
- `test_fifo_within_same_priority` in tests/test_queue.py remains
  unchanged and passing -- same-priority FIFO ordering for `put()` is
  a load-bearing guarantee and must not regress.
- A new test covering `Queue.extend()` is added, asserting that jobs
  come back out in the same order they were passed in.
- `Queue.extend([], priority=0)` is a no-op.

## Verification
- `pytest tests/test_queue.py`

## Definition of rejected
Throw away if extend changes the relative ordering of jobs enqueued
via plain `put()`.

## Time budget
expected 20m, stuck 60m
