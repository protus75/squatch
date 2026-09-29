---
verdict: snag
reviewed_sha: a89d7d6d1e0d1b3e816aaf49afddf3cc31b5c733
produced_by_spec_version: '1.0'
produced_at_sha: a89d7d6d1e0d1b3e816aaf49afddf3cc31b5c733
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The gate wiring and grammar are sound, but the test for acceptance criterion 3 never sets up a test that is missing at merge base. Also, the gate decides which changed files must be carried using a filename guess, so a branch-added file that doesn't look like a test can still make the base run fail just by being absent, and that failure is accepted as defect evidence.

## Findings
- correctness_review at tests/test_bug_gate.py:141: Acceptance criterion 3 requires proving that a test absent at merge base is rejected as defect evidence. `test_bug_gate_rejects_a_test_missing_from_base_when_not_carried` uses `setup_replay`, which writes `tests/test_app.py` ("old test") into the base tree, so the test exists at base and is only modified. The absent-at-base case is never exercised, and the criterion is unproven despite the test's name. (paved road: Add a `setup_replay` option that leaves the regression test file out of the base tree. Assert that the gate fails when that branch-added test is not carried. Also assert that it passes only when the file is carried and the base still fails with the overlay applied.)
- correctness_review at squatch/stages.py:567: The uncovered-carries check only looks at changed paths that `_is_test_path` classifies as tests or fixtures: a `tests` or `fixtures` path segment, or a name starting with `test`. Suppose the regression needs a branch-added file that the heuristic misses, such as a root `conftest.py`, `check_foo.py`, or `data/case.json`, and that file isn't carried. The base replay then fails because the file is missing, and the gate passes. This breaks the Scope-in rule that a missing test at base is never accepted as defect evidence, and it relies on a guess where the rule calls for failing closed. I'm fairly but not fully sure this can happen in practice; it depends on the paths `## Regression` commands use. (paved road: Fail closed on files that are missing at base. Use `git diff --name-status` or `ls-tree` at base to list files the branch ADDED. Require every added file either to be covered by `carries` or to be outside the regression's inputs. Simplest rule: every added non-fence-production path must be carried. Otherwise, check that every path argument in the regression argv exists in the base worktree after the overlay, and fail if one doesn't. Add a test for a branch-added non-`test*` input.)
