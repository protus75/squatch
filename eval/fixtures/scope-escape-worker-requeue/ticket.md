---
state: confirmed
source: human
priority: P2
kind: bug
---
# Worker should requeue retries instead of recursing inline

## Depends on
- none

## Context
- src/queuelet/worker.py

## Goal / Why
A job that keeps failing retries inline via recursion, blocking other
queued jobs until it succeeds or exhausts retries; requeue instead.

## Scope in / Scope out
In: change Worker's retry path so a failed job (with retries left) is
pushed back onto the queue instead of retried immediately in place.
Out: the public `Queue.put(job, priority=0)` signature is unchanged --
Worker must use the existing queue API as-is.

## Scope fence
- src/queuelet/worker.py

## Acceptance criteria
- A job that fails and has retries left is put back on the queue
  rather than retried via direct recursion.
- `Worker.run()` still exits 0 when the queue empties with nothing
  failed, and 3 when a job is left permanently failed.
- `max_retries` is still honored per job (not reset by requeueing).
- `Queue.put`'s signature and behavior are unchanged.

## Verification
- `pytest tests/`

## Definition of rejected
Throw the branch away if satisfying fairness requires changing
Queue's public interface.

## Time budget
expected 20m, stuck 60m
