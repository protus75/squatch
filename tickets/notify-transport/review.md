---
verdict: snag
reviewed_sha: 0c30274a021f4228024273dca19e75acd81c1a67
produced_by_spec_version: '1.0'
produced_at_sha: 0c30274a021f4228024273dca19e75acd81c1a67
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The executor isolation, config closure, Effect keys and Serve wiring are sound. Two defects remain: storm trips are only pushed after dispatch has created a hold for them, so the startup pass misses them, and some process-launch errors can crash the daemon.

## Findings
- correctness_review at squatch/notify.py:58: `_escalations` sends a storm-trip escalation only for a `control_hold` with trigger `storm_trip` whose `trip_id` matches a trip. It never sends from the `storm_trip` signal itself. Those holds are created lazily by `StormDispatchHold.holds_offer` (squatch/daemon.py:171-179), which runs only when dispatch offers the trip's `emitting_origin` stem. So a `storm_trip` journaled before a restart whose hold was never created is not pushed by the startup reconcile, which runs before any dispatch (a missed startup signal under the ticket's Definition of rejected). A trip whose origin is never offered again (a finished ticket, or an origin that is not a ticket) is never pushed at all. The ticket says the reconciler reads journaled `storm_trip` signals. `test_real_reconciler_pushes_startup_and_later_poll_signals` and `test_notify.py` hide this because they always journal the hold next to the trip. (paved road: Base storm escalations on the `storm_trip` signals themselves, keyed on `trip_id` plus `emitting_origin` as the ticket, so every journaled trip is pushed at startup whether or not a hold exists. Render the resume action from the matching hold if there is one, or tell the operator how to resume the pending trip. Add a startup test that journals only a `storm_trip` signal, with no hold, and asserts it is pushed before dispatch.)
- correctness_review at squatch/notify.py:34: The reconciler catches only `ExecutableNotFound`, `RuntimeError` and `TimeoutError`. `SubprocessExec.run` turns only `FileNotFoundError` into `ExecutableNotFound`, so other launch errors from `asyncio.create_subprocess_exec` escape: `PermissionError` (argv[0] not executable), `IsADirectoryError`, and other `OSError`s. They propagate out of `Serve.run`'s startup reconcile and out of the `watch()` callback. A misconfigured `config.notify` can therefore crash `serve` or break the watcher poll, instead of being reported through the daemon failure path while the durable intent is kept, as the ticket requires. (paved road: In `SubprocessNotifications.notify`, turn launch `OSError`s (other than the `FileNotFoundError` already handled as `ExecutableNotFound`) into the declared `RuntimeError` transport failure, or catch `OSError` in the reconciler next to the others. Add a seam test using a non-executable file as argv[0] and assert a reported failure with no completion journaled.)
