---
verdict: snag
reviewed_sha: dc7608a9ab18415d10a7e8aa816353805d37a982
produced_by_spec_version: '1.0'
produced_at_sha: dc7608a9ab18415d10a7e8aa816353805d37a982
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The production wiring, the durable hold/lifecycle rehydration and the CLI publish-or-apply paths look correct and satisfy the acceptance criteria inside the fence. One problem remains: the production routing test in tests/test_daemon_composition.py orders pause and resume with a 50ms real-time sleep. If it loses that race, the test hangs forever instead of failing.

## Findings
- correctness_review at tests/test_daemon_composition.py:150: test_main_drain_routes_control_after_inflight_work_and_before_the_next_offer publishes the pause during the first dispatch. It then relies on `asyncio.sleep(0.05)` to publish the resume only after the drain has consumed the pause. That ordering is not guaranteed. After the pipeline returns, the runner still diagnoses, journals and cleans up, and the drain re-folds the journal and runs `_scan`, which makes git subprocess calls through the process seam. All of that can take more than 50ms, especially on WSL. If the release file lands before the drain's next `allow_offer`, both requests are in the same inbox snapshot. `consume` snapshots `releasable` before the pause creates its hold, so the release is decided `stale` ('hold does not match') and the hold stays. `_wait_for_offer` then loops until the admission ceiling. The test injects `clock=lambda: NOW`, so `self._clock() < deadline` is always true and the test never ends. It passed in this check run only because the timing happened to work out. I could not re-run it here to measure how often it hangs, so the flake rate is unconfirmed, but the race is visible in the code. (paved road: Remove the wall-clock ordering. Trigger the resume from a deterministic signal that the pause was applied. For example, inject a `wait_for_control` or `sleep` into the factory through the drain's public `control_factory` path, and have it publish the resume the first time it is called, when the drain is provably paused. Alternatively, poll the journal for the pause's `control_hold` event before publishing the release. Also give the test a clock or a bound that fails instead of hanging if the drain stays paused.)
