---
verdict: approve
reviewed_sha: b297d5190c4d4c1888ebbc4c2e4c8adf1fe47a79
produced_by_spec_version: '1.0'
produced_at_sha: b297d5190c4d4c1888ebbc4c2e4c8adf1fe47a79
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diff connects the dormant control-inbox kill mutation to a real `Driver.run` invocation through `Driver.abort_active`, which cancels the task and waits for it to unwind without swallowing `CancelledError`. The tests use a real Driver and a real journal to prove the accepted and applied decision, the unwind wait, error propagation to the invocation's caller, and that cancelling the consumer is not swallowed. All changes stay inside the scope fence, and the check report is green.

## Findings
- none
