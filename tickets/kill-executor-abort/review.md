---
verdict: snag
reviewed_sha: 4f59fb67a4363bc9a60e5adb7bab2fff5b719bd4
produced_by_spec_version: '1.0'
produced_at_sha: 4f59fb67a4363bc9a60e5adb7bab2fff5b719bd4
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
Kill-to-Driver cancellation is wired correctly and both tests prove it: CancelledError propagates past the Driver's `except Exception` handler, and the journal records the kill as accepted and applied. One defect remains: `Driver.run` has an unreachable defensive branch that duplicates the whole call path.

## Findings
- correctness_review at squatch/driver.py:88: `Driver.run` handles `asyncio.current_task() is None` by calling `self._run(...)` a second time without tracking the task. That branch can never run because `run` is only ever awaited inside the asyncio event loop, where a current task always exists. It duplicates the full argument list in a second call path, and any invocation that took it could never be aborted. This is a branch that can never run, and it is the defensive parallel path the engine rules forbid. (paved road: Delete the `if active is None:` branch and keep one path: `self._active = asyncio.current_task()`, then `try: return await self._run(...)` with the existing identity-checked `finally` reset.)
