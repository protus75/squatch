---
verdict: approve
reviewed_sha: 3fc2fb10f214df6f5d6fc35b3bb61a383462e354
produced_by_spec_version: '1.0'
produced_at_sha: 3fc2fb10f214df6f5d6fc35b3bb61a383462e354
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diff adds a `kill` verb that goes through the lock-held control path. While a dispatch is running, the drain watches for kill requests alongside it. Kill sets the stopping flag, calls the Driver abort that Stages exposes, and waits for the Driver to unwind before the inbox journals applied. The drain checks the stopping flag before any later admission or retry draw. A stale kill changes nothing, and kill with no engine running refuses without creating control state. Every changed path is inside the scope fence, the predecessor contracts are unchanged apart from the migrated kill-verb assertion, and all checks passed.

## Findings
- none
