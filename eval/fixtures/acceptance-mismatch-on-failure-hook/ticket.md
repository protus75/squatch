---
state: confirmed
source: human
priority: P2
kind: feature
---
# Add an on_failure callback hook to Worker

## Depends on
- none

## Context
- src/queuelet/worker.py

## Goal / Why
Operators want to be notified the moment a job permanently fails,
instead of only inspecting `Worker.failed` after `run()` returns.

## Scope in / Scope out
In: an optional `on_failure` callback parameter on `Worker.__init__`,
invoked once per job that exhausts `max_retries`.
Out: `Queue` is untouched; retry/backoff timing logic is unchanged.

## Scope fence
- src/queuelet/worker.py

## Acceptance criteria
- `Worker(queue, handler, on_failure=cb)` calls `cb(job)` exactly once
  per job that exhausts retries, when it's added to `self.failed`.
- `on_failure` defaults to `None`; no callback fires if not provided.
- `Worker.run()` exits 0 when the queue is empty and 3 when a job is
  left failed -- this exit-code contract does not change.
- Existing retry/backoff behavior (`max_retries`, `compute_delay`) is
  unchanged.

## Verification
- `pytest tests/`

## Definition of rejected
Throw away if the hook requires changing the exit-code contract or
the queue's public interface.

## Time budget
expected 20m, stuck 60m
