---
verdict: snag
reviewed_sha: 4555f5e5df32bc264876c7e4aa990361d9e16cd8
produced_by_spec_version: '1.0'
produced_at_sha: 4555f5e5df32bc264876c7e4aa990361d9e16cd8
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The per-call ceiling is taken once, before each driver.run. The harness allows one re-prompt (RETRY_CAP = 1), so a single fixture can make two provider calls that each carry the same full remaining budget. Charged spend can therefore go past USD 5.00 before `_charged` notices, which breaks the cap criterion.

## Findings
- correctness_review at eval/harness.py:485: `with call_budget(_remaining_budget(spend))` wraps the whole `driver.run(...)`. Driver builds a new LLMRequest for every re-prompt (squatch/driver.py:120-126, retry_cap=RETRY_CAP=1), and each one reads the same ContextVar value. So both the first call and the re-prompt for a fixture carry the full remaining budget, not the budget left after the first call. Example: with $0.10 left, a first call costing $0.10 that returns an invalid artifact is followed by a re-prompt that may also spend up to $0.10. Charged spend reaches $5.10 before `_charged` raises Unscored after the fact. The Author call has the same problem: `call_budget(GO_SPEND_CAP_USD)` lets two $5.00 calls through. This breaks the criterion that every Author and Review request carries the remaining run budget and that charged spend never exceeds USD 5.00. The test suite has no re-prompt case, so it misses this. (paved road: Make each LLMRequest's ceiling the budget left at the moment it is created. One option: have the harness pass a per-call budget provider, or wrap `llm` in the harness so every call recomputes `GO_SPEND_CAP_USD - charged_so_far` (including earlier calls in the same driver.run) and refuses before the call when that is <= 0. Add a test in tests/test_go_grade.py where a Review reply is invalid, forcing a re-prompt. It should assert that the second request's max_budget_usd is lower by the first call's cost and that total charged spend stays <= 5.00.)
