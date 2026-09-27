---
verdict: snag
reviewed_sha: 258ed22c363446cdf9c9dd67621553156b120111
produced_by_spec_version: '1.0'
produced_at_sha: 258ed22c363446cdf9c9dd67621553156b120111
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The runner drives the production serve graph through injected seams for 24 injected hours and covers exactly the three members. However, the worker_killed_mid_run entry's terminal, disposition and producing run come from a second failure the harness plants, not from the worker kill.

## Findings
- correctness_review at eval/daemon_soak.py:218: In `_ScenarioProcess.run`, the harness makes the redispatched run's verification fail on purpose: `self._implement_calls == 2 and not self._worker_red` returns `1, '', 'planted re-run failure after worker reconciliation'`. The kill itself only abandons run 0. The `gate_failed` terminal, the Box disposition and `producing_run=<stem>/1` all come from this planted Check failure on run 1, which the kill did not cause. The runner's own `_FAULTS` table sets `expected` to `abandoned->gate_failed;redispatched=1`, and `green` is computed as observed == expected, so the harness chooses the outcome and then reports it as green. The runner test confirms that run 1 never reaches review. This conflicts with the ticket requirement that each field comes from 'that member's local run evidence' of the named fault, and it comes close to the 'self-attested report' rejection criterion. I may be wrong if plan section 20 or `tests/test_restart_timers.py` requires a failing redispatch to produce the disposition. If so, that requirement should be cited in the code. As written, the harness steers the result instead of observing it. (paved road: Remove the planted re-run verification failure. Let the redispatched run 1 end the way production ends it, and take `observed` from that real terminal. Take the disposition from whatever Box or escalation record production writes for the abandoned or redispatched run, and set `producing_run` to the run that record names. Set `expected` from the plan's intended outcome for a worker kill, not from the outcome the harness forces. If production writes no Box or alert for a clean recovery, don't invent one; park the ticket for plan repair so the plan can say which disposition this member should have.)
