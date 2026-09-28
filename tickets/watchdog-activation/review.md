---
verdict: snag
reviewed_sha: 942f3a484cbae99f3b27b921b7ac6647291d361a
produced_by_spec_version: '1.0'
produced_at_sha: 942f3a484cbae99f3b27b921b7ac6647291d361a
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The drain/serve binding, the Stages run binding, notify identities and the drain reconciliation match the ticket, and the checks are green. Two defects remain: the stuck signal can be silently dropped on a real hard timeout, and providers.py gains a new concurrency gate instead of reporting the existing provider-cap waits.

## Findings
- correctness_review at squatch/watchdog.py:283: abort_current writes the `stuck` signal only when `clock() - self._call_started >= stuck_minutes*60`. `_call_started` is set after registry resolution, slot acquisition and the first step of the wrapper task. LLMEffect._within_budget computes its deadline before it creates that task, and it sleeps on the loop's monotonic timer, which can fire up to clock_resolution early. On a real hard timeout the wrapper's measured elapsed time is therefore usually just under the budget, so no stuck signal is written and no page goes out. Any cap wait makes the shortfall certain. test_stuck_root_aborts_same_client_group_and_unwinds_stages hides this: it injects a sleep that advances the fake clock by exactly the budget. I am fairly but not fully sure this reproduces with real sleep; the margin is microseconds to milliseconds. (paved road: Measure from the start of WatchdogLLM.call, before resolve and the slot, and compare with a tolerance. Alternatively, record the stuck signal whenever abort_current runs while a bound call is in flight and past the budget minus a small epsilon. Add a test that uses LLMEffect's real clock/sleep pairing, not a sleep that advances the clock exactly.)
- correctness_review at squatch/providers.py:298: Registry.slot adds a new per-provider asyncio.Semaphore that blocks calls. That is new cap/reliability machinery; the scope-out forbids it, and providers.py is fenced for binding support only. Provider concurrency is already owned by squatch/thresh.py. The semaphore also cannot produce a real wait in production: compose() builds a fresh Registry per Stages, and a Stages instance makes one call at a time, so observe_cap_wait never fires outside the test's fabricated competitor. The criterion that real provider-cap wait intervals reach the detector is met only by the test harness. (paved road: Remove Registry.slot. Take cap-wait intervals from the existing provider-cap owner (thresh.py's hold decisions, or wherever a real provider-concurrency wait happens in the Stages call path) and pass the empty list when no such wait occurs. Do not add a new gate. If no production wait source exists yet, file that gap to the Suggestion Box rather than building a gate inside this ticket.)
