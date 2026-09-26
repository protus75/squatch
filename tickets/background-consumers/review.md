---
verdict: snag
reviewed_sha: ce82e56cdb3fe3c01bc864592b7e97dce73a3724
produced_by_spec_version: '1.0'
produced_at_sha: ce82e56cdb3fe3c01bc864592b7e97dce73a3724
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The owner's wiring and the three callback boundaries match the real Watcher.observed, Rework.run(sha=) and Triage.run(spec) signatures. But the public start()/shutdown() path throws away a callback's exception, no test shows the owner repeating any consumer, and box_consumer can spin the event loop.

## Findings
- correctness_review at squatch/daemon.py:150: shutdown() gathers with return_exceptions=True, so it throws away any exception a consumer task raised. If a caller uses the public start()/shutdown() pair, a failing callback dies silently, its siblings keep running until someone calls shutdown, and shutdown returns normally. The ticket says: 'If one callback raises, shutdown cancels and awaits siblings then re-raises that exception' (AC2: 'the owner's shutdown await re-raises that exception'). Only run() re-raises, and only for the exception gather surfaced first. That leaves two lifetime paths with different failure semantics. (paved road: Make shutdown() re-raise the first non-CancelledError exception from the awaited tasks after cancelling and awaiting all of them. Alternatively, make run() the only public lifetime entry point by making start() and shutdown() private. Add a test for whichever path stays public.)
- correctness_review at tests/test_daemon_tasks.py:11: The three per-consumer tests call each builder's callback once, directly. None of them runs the callback under DaemonTasks, and no test checks that the owner calls any callback more than once. The ticket requires one test 'for each consumer lifetime' and that the owner 'owns their repetition and lifetime', so both the lifetime and the repetition are untested. This is a partial miss on AC1. I am not certain whether a direct single call was meant to count as 'lifetime'. (paved road: For each consumer, start a DaemonTasks with that consumer's built callback in its slot (and blocking fakes in the other two). Assert the callback runs at least twice, e.g. the fake Watcher.observed or Rework.run records two calls. Then shut down and assert the task finished.)
- correctness_review at squatch/daemon.py:168: _repeat runs `while True: await callback()` with no point where it must hand control back to the event loop. box_consumer wraps triage.run(spec) directly, and a triage pass over an empty box presumably finishes without suspending. If so, the loop spins forever, starves the sibling consumers, and prevents shutdown's cancellation from ever being delivered. The same applies to watcher_consumer when the snapshot supplier returns immediately. I have not checked whether Triage.run always suspends, so I am unsure this happens in practice. (paved road: Make _repeat yield after each pass, e.g. `await asyncio.sleep(0)`, or pace it through the injected clock seam. Or state and test that each callback must block until there is work. Add a test in which an immediately-returning callback still lets its siblings run and shutdown complete.)
