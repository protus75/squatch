---
verdict: snag
reviewed_sha: efe5263a005a3bd93b4ce885a3eb63e27a5f6dae
produced_by_spec_version: '1.0'
produced_at_sha: efe5263a005a3bd93b4ce885a3eb63e27a5f6dae
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diagnosis seam, the Diagnoser's fixed decision order, the record shape, the terminal ordering, and the drain re-offer match the ticket, and every changed path is inside the fence. Two problems need fixing: the new prior-attempts render can show an older attempt's run record and spool tails under a 'latest' label, and one drain acceptance criterion is only partly tested.

## Findings
- correctness_review at squatch/stages.py:609: `latest` is now set only in the undiagnosed branch, so it points at the last attempt that has no verdict, not the last harvested attempt. Example: attempt 0's diagnosis ends `invalid_artifact` (verdict null) and attempt 1 is diagnosed `retry`. Attempt 2's prompt then shows attempt 0's run.md and spool tails under the headings 'latest run.md:' and 'latest non-prompt spool tails:'. The spine-harvest render showed those details only for the newest harvested attempt, and never for an older one, so the ticket's rule that an attempt with no verdict 'renders raw exactly as spine-harvest landed it' is broken. The run.md and tails are also labeled as the latest attempt when they are not. No test covers a mix of undiagnosed and diagnosed attempts. (paved road: Render run.md and spool tails only when the newest harvested attempt has no verdict: track the newest harvested attempt separately, and set the details source to it only if that attempt has no diagnosis verdict; otherwise render no raw details. Add a test_drain_reentry case with an attempt whose diagnosis call was `invalid_artifact`, followed by a diagnosed attempt, and assert the older attempt's run.md and spool tails are absent.)
- correctness_review at tests/test_drain.py:283: The criterion 'a stem whose `retry` cap is spent stays parked exactly as in Phase 1 whatever its verdict' has no test that sets a verdict. The existing spent-retry park test only covers the fake's default synthetic `abandon-human` record. No test shows that a `retry`, `escalate`, `reject`, `split`, or `invalid_artifact` diagnosis on a stem with a spent retry cap still parks without another retry draw. (paved road: Parametrize the spent-retry park test over the Scripted `diagnoses` records used in test_every_diagnosis_result_is_reoffered_and_reported. Assert the same park line, one retry draw, and no further dispatch for each verdict and call.)
