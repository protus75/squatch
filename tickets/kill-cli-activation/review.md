---
verdict: snag
reviewed_sha: f277410b86faa2638efe8e3bf4764c3361f10755
produced_by_spec_version: '1.0'
produced_at_sha: f277410b86faa2638efe8e3bf4764c3361f10755
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
Kill works while a dispatch is running and when no engine is running, but it does not stop a drain that is paused. The drain stays in its offer-wait loop and keeps the lock until the pause is released or max_runtime_hours runs out.

## Findings
- correctness_review at squatch/drain.py:249: `_wait_for_offer` loops `while not allow_offer(): await wait_for_control()`. When a pause hold is active, `allow_offer()` consumes the kill: `DrainControl.apply` sets `stopping=True` and the decision is journaled accepted and then applied. But `allow_offer()` still returns False because `hold_id` is set, so the loop never looks at `stopping`. The drain only reaches the new `if self._stopping: return self._killed()` check (lines 223 and 231) after a resume or when the ceiling timer fires (which reports `halted`, not `stopped`). So `squatch kill` on a paused drain prints `published kill` and journals `applied: true`, yet the engine keeps running and holding the lock, possibly for hours. The ticket requires the lock holder to stop and leave the run terminal or restart-reconcilable before lock release. That is not met on this path, and no test in tests/test_kill_cli_activation.py covers kill-while-paused. (paved road: Make the offer wait stop on the latch. Either `_wait_for_offer` returns as soon as `self._stopping` is true, with the caller checking `_stopping` before treating the result as a ceiling halt, or `DrainControl.allow_offer` returns True once `stopping` is set so the existing post-wait `_stopping` check returns `_killed()`. Add a case to tests/test_kill_cli_activation.py: pause the live drain, run kill, and assert that the drain returns `stopped: kill accepted`, releases the lock, and admits no further dispatch or retry draw.)
