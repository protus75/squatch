---
verdict: snag
reviewed_sha: 8ef42ab600592c7778e6f5773294f077b0cfcb1e
produced_by_spec_version: '1.0'
produced_at_sha: 8ef42ab600592c7778e6f5773294f077b0cfcb1e
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The reader, the Author wiring and the removal of `go_binds` are correct, and the checks are green. However, the diff deletes starting-state policy tests that never depended on `go_binds`, and the reader still binds when a `spec_major` value is a boolean instead of an integer.

## Findings
- correctness_review at tests/test_policy.py:21: The ticket requires `tests/test_policy.py` to prove that starting-state policy is still intact. The diff deletes `test_bypass_forces_every_policy_row_to_draft`, the 7-row check that `bypass=True` forces `draft` for every message_class and bug_origin row. That test never called `go_binds`. The diff also deletes the check that every policy row is `draft` without a binding GO (`go_binds=False`) for all four message classes and every bug_report origin/repro row. Only one `failure_report` go_binds=False case is left. This reduces coverage of the policy the criterion says must stay intact. (paved road: Put back the parametrized bypass test unchanged. Put back the every-row `go_binds=False -> draft` loop, dropping only its `go_binds(cfg, ())` assertion. Remove only assertions that reference the deleted `policy.go_binds`.)
- correctness_review at squatch/baseline.py:58: Malformed `spec_major` values are not fully rejected. `_matches` only checks that `spec_major` is a dict with keys {review, author}, then compares it with `majors == expected_majors`. In Python `True == 1`, so a GO record with `spec_major: {"review": true, "author": true}` still resolves to GO with binds=true when the current specs are 1.x. The ticket requires malformed spec fields on a selected GO to give REVOKED. (paved road: Require each `spec_major` value to satisfy `type(value) is int` before comparing (for example, `if any(type(v) is not int for v in majors.values()): return False`). Add a case with `{"review": True, "author": True}` to `test_malformed_baseline_fields_revoke`.)
