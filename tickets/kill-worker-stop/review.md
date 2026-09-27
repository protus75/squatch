---
verdict: snag
reviewed_sha: 4f2c6bcd7f26be630f07697cb457d719fdde65af
produced_by_spec_version: '1.0'
produced_at_sha: 4f2c6bcd7f26be630f07697cb457d719fdde65af
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The executor-unwind-then-cancel sequence in kill_worker_stop_consumer/stop_workers is correct under start(), but the new test does not prove the applied decision comes after the workers are observed. The kill also cancels its own control consumer when DaemonTasks is driven by run().

## Findings
- correctness_review at tests/test_kill_worker_stop.py:95: Acceptance criterion 1 is not proven. The test never checks that the applied=True control_decision is absent while the workers are blocked in their cancellation handlers. It only looks for applied=True after release_workers.set(). A mutant stop_workers that cancels the workers without awaiting them would journal the applied decision early and still pass this test. The same gap exists before active.unwind.set(): only the accepted (applied=False) decision is checked, and the absence of applied=True is never asserted. (paved road: Before release_workers.set(), and again while active.unwind is unset, read the journal and assert it has no control_decision for the request with applied=True, e.g. with a non-waiting helper that returns whether a matching decision exists. That makes the ordering 'observation -> applied decision' an actual assertion.)
- correctness_review at squatch/daemon.py:228: stop_workers cancels sibling tasks that DaemonTasks.run() is still awaiting through asyncio.gather(*self._tasks), which is called without return_exceptions. Under run(), the first cancelled worker makes that gather raise CancelledError. run() then catches it with `except BaseException` and calls shutdown(), which cancels the control task while it is still inside stop_workers/inbox.consume. So the control consumer performing the kill is cancelled, the applied decision is never journaled, and run() ends. That is exactly what the ticket's Why forbids. The tests only exercise start()+shutdown(), so they miss this. This is a latent defect because the composition is dormant, but the ordinary run() entry point cannot host this kill boundary as written. (paved road: Keep run() working with a worker-only stop without changing its ordinary behavior. For example, have run() await the control task and the worker tasks such that a worker cancellation caused by stop_workers does not trigger shutdown(): track that the workers were deliberately stopped and re-await the remaining tasks. Add a test in tests/test_kill_worker_stop.py that drives the kill through owner.run() and asserts the applied decision is journaled and the control task is not cancelled.)
