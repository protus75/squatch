---
verdict: approve
reviewed_sha: cba8ba060a4a2d4bca5baa52b372e09b9953ce19
produced_by_spec_version: '1.0'
produced_at_sha: cba8ba060a4a2d4bca5baa52b372e09b9953ce19
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diff adds the `serve` verb and the new squatch/serve.py production graph. Serve composes every named daemon boundary inside the runner's reconciled, lock-held session, and kill control applies its decision before mutating state and unwinds the executor before cancelling workers. Every changed path is inside the fence, the read-only component modules are untouched, and all checks pass.

## Findings
- none
