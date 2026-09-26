---
verdict: snag
reviewed_sha: 759770da7ef3e4665537b8e2a2208c0b23b60cbc
produced_by_spec_version: '1.0'
produced_at_sha: 759770da7ef3e4665537b8e2a2208c0b23b60cbc
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The pause boundary, the hold-bound release, and the drain hook ordering for fresh offers and retries are correct, and the checks are green. One problem: the test meant to pin construction dormancy cannot fail, so it does not pin the dormancy the ticket asks for.

## Findings
- correctness_review at tests/test_daemon_pause.py:116: The ticket asks for a direct test that pins construction dormancy for pause-resume-activation to migrate. `test_pause_construction_is_dormant_in_daemon_control_composition` asserts `not isinstance(control, DispatchPause)` on the result of `compose_daemon_control`, but that function is typed to return `ControlInbox`, and `DispatchPause` is not a `ControlInbox` subclass. The assertion is therefore always true. The only production site that could activate the pause is the CLI's construction of `Drain`, where `pause` defaults to `None`, and no test covers it. A successor could wire a `DispatchPause` into the CLI drain or the daemon and this test would still pass. That leaves the dormancy criterion effectively unmet. (paved road: In tests/test_daemon_pause.py, assert the production defaults directly. Build `Drain` the way the CLI does, or capture its constructor kwargs by monkeypatching `squatch.__main__.Drain`, and assert that its `_pause` is `None` or that no `pause` kwarg is passed. Also assert that `compose_daemon_control` returns an inbox with no holds and that the daemon composition exposes no `DispatchPause`. The successor then has a concrete assertion to flip when it activates the pause.)
