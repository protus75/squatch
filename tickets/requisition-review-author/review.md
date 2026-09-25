---
verdict: snag
reviewed_sha: 12711ad5331e5933a08cbb08f856f147771e096a
produced_by_spec_version: '1.0'
produced_at_sha: 12711ad5331e5933a08cbb08f856f147771e096a
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The wiring, driver hook, and verdict recording look correct, but the Author target resolver copies the ticket-schema grammar check instead of reusing it, and the copy has already drifted: it crashes when the repo has no plan file. The driver test also never checks that findings are preserved on a terminal stop.

## Findings
- correctness_review at squatch/author.py:110: `_ReviewCapture.targets` copies `TicketSchemaGate.check`'s grammar check, and the copy has already drifted. It calls `(self._repo / PLAN_FILE).read_text()` with no guard, while `TicketSchemaGate` passes `plan=None` when `SQUATCH_PLAN.md` is absent. In a host repo with no plan file, every grammar-valid ticket raises FileNotFoundError inside the resolver. `run_gates` turns that into a hard 'gate crashed' `requisition_review` finding, so the Author re-prompts until the retry allowance runs out and can never commit. This breaks the ticket's requirement that the resolver use the same complete ticket-schema predicate as `TicketSchemaGate`, and the acceptance line that the two 'cannot drift on grammar admission'. (paved road: Don't copy the check. In `targets`, run the same predicate `TicketSchemaGate` runs: either `await TicketSchemaGate().check(artifact, workspace)` from an async resolver path, or move the stem, reserved-stem and `lint_ticket` logic into one shared function that both call. Return the target only when that verdict is pass. Add a test in tests/test_author.py where the repo has no SQUATCH_PLAN.md and a valid ticket still reaches review and commits.)
- correctness_review at tests/test_driver.py:459: The acceptance criterion says the `terminal_findings` hook 'preserves all findings'. `test_terminal_findings_stop_without_changing_the_every_gate_rule` only checks that both gates ran and how many calls were made. It never asserts that `result.findings` contains the findings from both failing gates, so a regression that dropped findings on the terminal path would still pass. (paved road: In the `terminal_findings` case, assert that `result.findings` equals the combined hard findings of `first` and `second`, for example by checking its length and codes against both StubGate reports.)
