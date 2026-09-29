---
verdict: approve
reviewed_sha: 75ce23ec9caa078dd364667210906ec8fd9462ee
produced_by_spec_version: '1.0'
produced_at_sha: 75ce23ec9caa078dd364667210906ec8fd9462ee
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diff moves the routing-to-conduct-file mapping into one function, `providers.conduct_files`, which both `_core` and the new hard `CoreDrift` gate call. The gate runs in the merge-time regate and reaches `hostfiles.classify` against the branch's CORE when squatch reviews itself and the engine's CORE otherwise. It refuses malformed markers as located findings, never writes to project files, and every changed path is inside the fence. All three acceptance criteria are met by the named tests, the renderer purity test is kept, and the check report is green.

## Findings
- none
