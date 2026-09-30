---
verdict: snag
reviewed_sha: 269d8eae18d6150379212e4e4d642e24f431a7af
produced_by_spec_version: '1.0'
produced_at_sha: 269d8eae18d6150379212e4e4d642e24f431a7af
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The report file exists in the worktree and record_go now refuses incomplete reports. But run_go_grade returns partial NO-GO evidence only when the pre-review floor check stops the loop. If the cap runs out during a later review after at least one scorable review, it still raises Unscored.

## Findings
- correctness_review at eval/harness.py:537: The scope asks that reaching the fixed cap after at least one scorable review journal and return the measured partial result instead of raising Unscored. The new code only handles this before a review starts: can_start_review compares the remaining budget with the largest earlier review cost, and that is a guess. Example: review 1 costs $1.00; review 2 starts with $3.95 left and uses it all through the per-call max_budget_usd ceiling or a re-prompt. Then one of three things raises Unscored even though scores is non-empty, and no NO-GO report is produced: _BudgetedLLMEffect.call raises through require_remaining on a re-prompt; _charged raises; or the branch `if result.outcome not in ("ok", "invalid_artifact"): call.require_remaining(); raise Unscored(...)` runs. The new test only covers the pre-check path, so this case is untested. (paved road: If the cap is exhausted inside a review, stop the loop and return the partial report whenever scores is non-empty, whether it shows up as Unscored from require_remaining/_charged during driver.run or as a non-scorable outcome with no budget left. Leave the incomplete review out of scores. Keep the spend total at or under $5.00. Add a test in tests/test_go_grade.py where the first review is cheap and the second review uses up the cap mid-review; assert the partial NO-GO report, that no further model call is made, and that record_go refuses the report.)
