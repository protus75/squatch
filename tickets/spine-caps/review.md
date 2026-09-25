---
verdict: approve
reviewed_sha: 52dd41ea0363a45dc6265832d8cb460c34421e53
produced_by_spec_version: '1.0'
produced_at_sha: 52dd41ea0363a45dc6265832d8cb460c34421e53
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diff adds squatch/caps.py with one cap vocabulary, one cap_consumed writer and one lineage fold. It moves the drain's and driver's retry accounting onto that module in place, makes the runner draw one infra unit before the infra_error and timeout terminals, and adds the retry-not-above-diagnosis config refusal. Every acceptance criterion is covered by a matching test, every changed path is inside the fence, and all checks are green.

## Findings
- none
