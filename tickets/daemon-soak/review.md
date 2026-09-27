---
verdict: approve
reviewed_sha: 89db774721100d1c56b6780e859e4205a591e0f0
produced_by_spec_version: '1.0'
produced_at_sha: 89db774721100d1c56b6780e859e4205a591e0f0
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diff adds a closed DaemonSoakReport schema to squatch/artifacts.py. It forbids extra fields, fixes the three members and their order, derives green from its inputs and requires injected_hours of at least 24. squatch/stages.py registers the schema in KNOWN_ARTIFACTS. eval/daemon_soak.py writes the report only to the uncommitted worktree outbox. The tests prove that registered validation runs, that the ordinary lane lifts the report without the ticket branch committing it, and that an invalid report is refused before any write. Every changed path is inside the fence, and the check report is green.

## Findings
- none
