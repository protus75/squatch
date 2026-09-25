---
verdict: snag
reviewed_sha: 3df2d6ac6b2aeb0c81e6e0ca3fc8a6535cb5df28
produced_by_spec_version: '1.0'
produced_at_sha: 3df2d6ac6b2aeb0c81e6e0ca3fc8a6535cb5df28
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diff meets every acceptance criterion and stays inside the fence, and the check report is green. One logic defect: `Drain._tail` gained a fallback `raise AssertionError` branch that can never run.

## Findings
- correctness_review at squatch/drain.py:352: In `_tail`, the new `else: raise AssertionError("an unspent retry cap has no remaining budget")` branch can never run. `spent()` is checked first and returns the retry reason whenever `drawn >= caps.retry`. `retry_budget()` is `caps.retry - drawn`, so any stem that gets past the `spent` check has `left > 0` and takes the `elif (left := ...) > 0` branch. The new branch is a defensive parallel path that engine code never reaches, and the project conduct forbids those ('No dual-path code'). It also replaces the old reachable `else` (the spent-cap road) with a crash path instead of a report line. (paved road: Delete the `raise AssertionError` branch and change `elif (left := self.retry_budget(facts, stem)) > 0:` into a plain `else:` that computes `left = self.retry_budget(facts, stem)` and builds the `{left} retry unit(s) left; {CONTINUE} re-offers it findings-fed` road. The `spent` branch above it already covers the zero-budget case.)
