---
verdict: approve
reviewed_sha: 4f9b6ecd476b095ffbd6cd482d75e498394f70e9
produced_by_spec_version: '1.0'
produced_at_sha: 4f9b6ecd476b095ffbd6cd482d75e498394f70e9
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diff adds a nullable, validated emitting_origin that the producer takes from the Box message origin, and replays legacy events lacking it as None. It holds only the offered stem that matches a trip origin: the hold decision is journaled before rehydration, and the hold is enforced in _wait_for_offer before any retry draw. Release goes through the identity- and lifecycle-bound control inbox, which keeps it separate from manual-pause and merge-admission holds. The hold is bound in the live drain CLI root, and the check report is green.

## Findings
- none
