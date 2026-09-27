---
verdict: snag
reviewed_sha: 65176a522346303065c39d54ae75080e77842956
produced_by_spec_version: '1.0'
produced_at_sha: 65176a522346303065c39d54ae75080e77842956
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The kill wiring and test meet the acceptance criteria, but Driver.abort_active swallows every CancelledError it catches, including one aimed at the control consumer awaiting it, so a daemon shutdown that cancels the consumer mid-abort is silently absorbed.

## Findings
- correctness_review at squatch/driver.py:107: `try: await active` / `except asyncio.CancelledError: pass` cannot tell the aborted invocation's cancellation apart from the caller's own. If the task running `abort_active` (the control consumer driven by DaemonTasks) is cancelled while it waits for the unwind, the CancelledError is raised in that task and discarded here. The consumer then returns normally instead of propagating its cancellation. That is a swallowed, mis-scoped exception, and it contradicts the ticket's requirement that cancellation is not swallowed. A second problem: a non-CancelledError that the aborted invocation raises while unwinding is re-raised into the control consumer, even though that exception belongs to the active caller. (paved road: Wait for the unwind without taking the task's result, e.g. `active.cancel(); await asyncio.wait({active})`. That observes completion, raises nothing from `active`, and still lets the caller's own CancelledError propagate. Alternatively, keep the try/except but re-raise when `asyncio.current_task().cancelling()` is non-zero. Add a test that cancels the task awaiting `driver_abort_consumer(...)()` during the unwind and asserts it raises CancelledError.)
