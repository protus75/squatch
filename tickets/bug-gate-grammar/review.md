---
verdict: snag
reviewed_sha: 8f864f21ac567dd88e5d025d77d93e4d03f34fa8
produced_by_spec_version: '1.0'
produced_at_sha: 8f864f21ac567dd88e5d025d77d93e4d03f34fa8
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The grammar, gate wiring and happy-path tests are sound, but the base comparison can still accept a test that is missing at merge base when that test lives in an existing file. The tests also never show the gate rejecting a merge-base run that passes, or a branch-head run that fails.

## Findings
- correctness_review at squatch/stages.py:488: The overlay only accepts files that are absent at merge base: `missing_overlay` rejects any carried path that already exists there. `uncovered` only catches wholly new files. So a regression test added to an existing test file (e.g. a new `test_x` in `tests/test_foo.py`, with `## Regression` running `pytest tests/test_foo.py::test_x`) cannot be carried, and nothing flags it. At merge base the old file runs, pytest fails with 'not found' (exit 4), and `base_rc != 0` is accepted as defect evidence. That is exactly the vacuous missing-test case the Scope in / Scope out and plan section 7 forbid ('must fail -- for the defect, not for a missing test'). Uncertainty: the plan's `carries` wording says 'branch-added' files, but the gate still has to reject this case rather than pass it. (paved road: Make the gate sound for tests inside modified files. Either allow `carries` to name branch-modified test/fixture files and overlay their branch content, or reject any `## Regression` whose command only works because branch-modified files are changed (e.g. fail when the diff touches a file under a `carries`-style test prefix that is not carried). Add a test in tests/test_bug_gate.py where the regression test is appended to a file that exists at base, and assert the gate does not pass on that.)
- correctness_review at tests/test_bug_gate.py:115: Acceptance criterion 2 and the Definition of rejected ('an unsound base comparison') need proof that the gate's pass/fail comparison is enforced. No test covers (a) the merge-base run with the carries overlay PASSING, meaning the defect was not reproduced, which must fail the gate, or (b) the branch-head run failing, which must fail the gate. Only the accept path and the uncovered-file rejection are tested, so the `base_rc == 0` and `head_rc != 0` branches in BugEvidence.check could be inverted or removed without any test going red. (paved road: Add tests to tests/test_bug_gate.py. Case (a): base `app.py` already returns 'animal' (or the regression asserts something true at base); assert `not run.passed` and the finding mentions 'merge base with carries overlay'. Case (b): the branch leaves the defect in place; assert `not run.passed` and the finding mentions 'branch head'.)
