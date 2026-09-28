---
verdict: approve
reviewed_sha: c6b37d83d431cebcaa26e61c68b852dc4a900251
produced_by_spec_version: '1.0'
produced_at_sha: c6b37d83d431cebcaa26e61c68b852dc4a900251
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diff adds a closed local RetroArtifact and a `retro` LLMStage that runs through the shared Driver. Reports commit straight to main at tickets/retro/<seq>.md with effect key `retro/<seq>`, the N/M/S due checks and forced boundaries match the ticket, and failures are window-suppressed and deduped by Box origin. The Drain hook is off by default, every changed path is inside the fence, and the check report is green.

## Findings
- none
