---
id: tombstone-000065
kind: tombstone
link: decision-000054
reopen_after_days: 90
message: box-000065-0c275afb
---
This duplicates decision-000054. That decision ruled on the same point: when a call does not report `input_tokens`/`output_tokens` (None), the run-level fold adds them into `Cost.tokens` as 0 and still sums `usd`, while the journal's `effect_completion` cost keeps the per-call token fields nullable, as section 6 types them. The fold is now the `_CostFold` class in squatch/driver.py:179, and its comment at :192 ('Unreported usage counts as zero tokens; the usd field still ...') states the same rule decision-000054 cited under the old name `_CostMeter.fold`. Only the name changed, not the behaviour. decision-000054 already named the one remaining gap: the section 5 `Cost` comment does not state the None-to-0 fold. It judged that a spec clarification the code already follows, blocking nothing and not causing a wrong regeneration. It also set the reopen trigger: add one line to the section 5 Cost comment if a consumer is found treating unreported usage as a measured zero in a misleading way. This message brings no new evidence, no consumer that misreads the fold, and no regeneration failure. It repeats the plan-wording request that decision-000054 already recorded as no-action. Reopen on the same trigger as decision-000054, or if a plan regeneration produces a `Cost.tokens` fold that differs from `_CostFold`'s.
