---
verdict: approve
reviewed_sha: 92218704ff5289bf0d5c65d04b54855187d50ebb
produced_by_spec_version: '1.0'
produced_at_sha: 92218704ff5289bf0d5c65d04b54855187d50ebb
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diff adds squatch/ladder.py, which does the model-first rung walk with the same-model skip, the rung fold bounded by an operator keep, the effective (tier, effort) resolution, and the identical, same-wall and oscillation detectors. It wires the ladder arms into reject.route after the spent-cap and null-verdict arms, records routed: ladder and the rung on the runner's terminal (the Reject arrival is written only for reject_queue), resolves the effective capability at every dispatch via dataclasses.replace without writing ticket.md, and passes the rung through the single caps.consume writer from the drain's re-offer. Every acceptance criterion has a matching test, every changed path is inside the fence, and all checks are green.

## Findings
- none
