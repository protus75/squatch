---
verdict: approve
reviewed_sha: 7ea945040facaf30bcf5fc1ff70c1e3b7a8e7fb8
produced_by_spec_version: '1.0'
produced_at_sha: 7ea945040facaf30bcf5fc1ff70c1e3b7a8e7fb8
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diff adds the lock-held manual `retro` verb through the one `_compose_retro` factory, which the drain hook also uses, and it creates no second model client or report writer. It adds a provider-free, read-only `doctor` that runs the five checks in order. Retro output and exits of 0, 1 and 2 match the contract. Every changed path is inside the fence, the check report is green, and each acceptance criterion is covered by its named test file.

## Findings
- none
