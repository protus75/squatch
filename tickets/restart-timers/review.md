---
verdict: snag
reviewed_sha: 26d2fe04df9bce80b0c3af71ba310ed054c1b2bb
produced_by_spec_version: '1.0'
produced_at_sha: 26d2fe04df9bce80b0c3af71ba310ed054c1b2bb
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The timer fold and the dispatch-ordered restart hook are sound and inside the fence. Two problems remain: the restart test never shows that the existing reconcile path is the delegate, and the timer tasks composed in __main__ are never shut down, so they can outlive their journal.

## Findings
- correctness_review at tests/test_restart_timers.py:35: Acceptance criterion 1 requires proof that restart composition delegates orphan reaping to the existing reconcile path. The test passes a stub `reaper=reap` into `compose_daemon_restart`, so `squatch.reconcile.reconcile` is never exercised or asserted. The test proves ordering against an arbitrary callable, not delegation to reconcile. The no-reaper branch of `compose_daemon_restart`, which is the production default, is also untested. A regression that pointed `Restart` at a second reap implementation would still pass. (paved road: Add an assertion that the default composition binds the existing reconciler. One way is `compose_daemon_restart(...)` without `reaper`, checking that its reaper `is squatch.reconcile.reconcile`. Another is to monkeypatch `squatch.reconcile.reconcile`, or the name `restart.py` imported, and assert it ran before the first dispatch. Keep the stub-based ordering test as well.)
- correctness_review at squatch/__main__.py:335: `factory` creates a `Timers` per journal through `compose_daemon_timers`. `rearm()` immediately starts `asyncio` tasks for any pending deadlines. Nothing ever calls `Timers.shutdown()`, and the `timers` dict holds the tasks past `Runner.session` exit. A re-armed deadline that elapses after the session closes its journal would call `journal.append` on a closed journal from an orphaned task. The result is an unretrieved task exception, or a write outside the lock scope. asyncio.run cancels leftover tasks only at loop teardown. This is the 'resources never released' class. Severity depends on whether Journal.append on a closed journal raises; I have not confirmed that. (paved road: Scope timer lifetime to the session that owns the journal. Shut down, with `await timers.pop(journal).shutdown()`, at the same teardown that closes the journal. If no teardown hook is reachable inside the fence, compose timers where the session's lifetime is visible and shut them down before the session exits. Add a test that a pending timer task does not outlive the journal.)
