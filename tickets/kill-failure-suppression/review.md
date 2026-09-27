---
verdict: snag
reviewed_sha: fcad181504e13aea6219659d1bfc5af66f4b4d19
produced_by_spec_version: '1.0'
produced_at_sha: fcad181504e13aea6219659d1bfc5af66f4b4d19
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The daemon.py change is sound: suppression is keyed to a flag that only the accepted-kill mutation sets, independent worker errors still surface through the control task, and external cancellation still propagates. But the stale-kill test never uses the kill composition, so it cannot prove that a stale kill leaves suppression off.

## Findings
- correctness_review at tests/test_kill_failure_suppression.py:104: test_stale_kill_does_not_suppress_an_independent_worker_failure builds its control consumer as `control_consumer(inbox, lambda _request: waiting())` instead of `kill_worker_stop_consumer(inbox, driver, owner)`. Nothing in that setup can ever call `stop_workers_for_kill` or set `_kill_stopping`, so the test would still pass if a stale kill wrongly enabled suppression (for example, if the stale gate in the kill path regressed). That leaves the criterion 'proves stale kills ... are not suppressed' unmet at the real daemon boundary the ticket requires. The test also checks only that a worker failure propagates after a stale decision. It never checks that the stale kill did not stop the workers or set the suppression state. (paved road: Wire the stale test through the real kill boundary: build the owner with a control callback that awaits `kill_worker_stop_consumer(inbox, ActiveDriver(), owner)()`, the same pattern as `owner_for`. Publish a kill with a foreign lifecycle and wait for its `stale` decision. Then assert the workers were not cancelled and that `owner._kill_stopping` is still False, and trigger the independent worker failure to show it propagates as RuntimeError from `run()`.)
