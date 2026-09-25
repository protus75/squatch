---
verdict: snag
reviewed_sha: 921d5328ebdc244f9321b5860d40441051758066
produced_by_spec_version: '1.0'
produced_at_sha: 921d5328ebdc244f9321b5860d40441051758066
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The implementation looks correct and stays inside the fence, but tests/test_terminal.py never checks the journal-order criterion: nothing pins the harvest lift's ticket-plane commit before the terminal state_transition.

## Findings
- correctness_review at tests/test_terminal.py:193: Acceptance criterion 3 says that in tests/test_terminal.py, for a non-ok run, the journal order is the harvest lift's ticket-plane commit first, then the run's terminal state_transition naming tickets/<stem>/attempts/<n>. The updated tests only compare d.transitions() and check that the worktree is gone and the branch exists. No test reads the lift effect (key lift/<stem>/<n>/harvest, effect_completion carrying a non-null commit) or checks that it comes before the terminal state_transition in d.events(). Because the harvest body field is only set after the lift returns, the code probably journals in the right order, but the ordering that criterion 3 requires is not pinned by any test, so a regression that journals the terminal before the harvest commit would still pass. (paved road: In the parametrized non-ok terminal test (or a new test in tests/test_terminal.py), take d.events() and find the index of the effect_completion whose key is lift/<STEM>/0/harvest and whose body.result.commit is not None. Assert that this index is lower than the index of the final state_transition to the terminal outcome, and assert that the commit is on main.)
