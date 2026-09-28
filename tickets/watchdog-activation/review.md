---
verdict: approve
reviewed_sha: 67da57554d1463e1a663063f812a1fe820afdd65
produced_by_spec_version: '1.0'
produced_at_sha: 67da57554d1463e1a663063f812a1fe820afdd65
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diff binds a watchdog-owned wrapper around the production CliClient inside the Stages-owned Driver for drain and serve, and review calls are included. It journals soft signals (ticket + run_seq) and stuck signals before notification, and extends the reconciler for those identities. It adds startup and per-dispatch reconciliation to drain over a private transport with provider keys removed from its environment, and migrates the named dormancy and notify tests. Every acceptance criterion is met, every changed path is inside the fence, and all checks pass.

## Findings
- none
