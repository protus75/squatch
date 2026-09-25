---
state: confirmed
source: human
priority: P2
kind: feature
---
# Add Queue.peek() for non-destructive head inspection

## Depends on
- none

## Context
- src/queuelet/queue.py

## Goal / Why
A health-check endpoint needs to report what job is at the head of the
queue without consuming it, so operators can see what's about to run
next.

## Scope in / Scope out
In: a `peek()` method on `Queue` returning the next job without
removing it, mirroring `get()`'s empty-queue handling.
Out: CI configuration is unchanged; this is a queue-module-only change.

## Scope fence
- src/queuelet/queue.py
- tests/test_queue.py

## Acceptance criteria
- `Queue.peek()` returns the same job `Queue.get()` would return next.
- Calling `peek()` does not change `len(queue)`.
- `Queue.peek()` on an empty queue returns `None` (matches `get()`).
- Existing queue tests keep passing unmodified.

## Verification
- `pytest tests/test_queue.py`

## Definition of rejected
Throw the branch away if implementing peek requires popping and
re-pushing the heap (must be O(1) inspection of the existing heap).

## Time budget
expected 20m, stuck 60m
