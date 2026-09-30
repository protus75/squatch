---
verdict: snag
reviewed_sha: 721a599d45e33a8333e644e24319964142b1038f
produced_by_spec_version: '1.0'
produced_at_sha: 721a599d45e33a8333e644e24319964142b1038f
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
Schema, registration and fence are sound and checks are green. But the report-to-regression and escape-attribution evidence is hardcoded, not taken from what serve did. That is the fabricated evidence the ticket's Definition of rejected names, and the tests only check the hardcoded strings.

## Findings
- correctness_review at eval/host_loop.py:170: The report_to_regression_bug_loop entry is fabricated. The harness writes the `fixture-regression-fix` bug ticket itself (via `_SCENARIOS`/`_ticket`), even though the comment says the Author result from the report inbox is the third ticket. The report dropped into `.squatch/report-inbox` is never linked to any merge. The entry reuses the producing_run of the ticket the harness wrote and hardcodes the observable `report-inbox->bug-ticket->merged`. The test asserts all three merged scenarios are the harness's own stems, which shows the ticket serve authored from the report is not among the recorded merges. (paved road: Do not pre-write a ticket for the report-to-regression scenario. Let serve's Author stage turn the inbox report into the bug ticket. Get the bug-loop entry from the journal: the report intake event, then the authored bug ticket's stem, then that ticket's `merged` transition and run_seq. Test that the stem came from the report, not from the harness.)
- correctness_review at eval/host_loop.py:174: The escape_attribution entry is a constant: observable `machine merge retained squash provenance` with the escape merge's run. Nothing checks provenance, a squash trailer, or an escape attributed back to a machine-introduced merge. Escape attribution is recorded without ever being observed. (paved road: Run the machine-introduced-escape scenario so an escape is detected and attributed. Read the attribution from the journal or the merge commit's trailers (git through the wrapper), fail if it is absent, and record the observed value and its producing run. Add a test that fails when attribution is missing.)
- correctness_review at tests/test_gates.py:128: `test_registering_terminal_schemas_does_not_construct_terminal_artifacts` searches a fresh, empty `tmp_path` and runs no code. It always passes, so it does not prove 'construction produces no terminal artifact' for tests/test_gates.py as the third acceptance criterion requires. (paved road: Run the relevant gate or registration path against a tmp repo (for example, validate or lift a HostLoopReport through the gate code under test). Then assert that neither `host-loop-report.json` nor `exit-receipt.json` exists in that repo.)
