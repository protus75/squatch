---
verdict: approve
reviewed_sha: c903137adf3b78e063a88ef32ebdd5c43163472a
produced_by_spec_version: '1.0'
produced_at_sha: c903137adf3b78e063a88ef32ebdd5c43163472a
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diff adds the `shakeout-tickets.bad_schema` member, registers it as the first entry in `GROUPS`, and adds a `test_tickets.py` unit pin. That pin checks that a committed `priority: P9` ticket is reported `held:` with the `ticket_schema` finding and its paved road, and that no `state_transition` is journaled for it. All changed paths are inside the fence, no path under `tickets/` is in the diff, and every check in the report passed, including verification.

## Findings
- none
