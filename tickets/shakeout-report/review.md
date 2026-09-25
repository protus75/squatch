---
verdict: approve
reviewed_sha: 4ec061a48f53010965fcc4c068ebc562ff6d7965
produced_by_spec_version: '1.0'
produced_at_sha: 4ec061a48f53010965fcc4c068ebc562ff6d7965
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diff adds the closed shakeout report schema, registers it in KNOWN_ARTIFACTS, validates known outbox files before the one existing lift path writes them, and turns a refusal into the invalid_artifact terminal at the only worktree lift call site. It also adds the bench, the empty registry, the run/check runner with the double gate, and tests for every acceptance criterion; all changed paths are inside the fence and every check is green.

## Findings
- none
