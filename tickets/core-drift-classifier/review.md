---
verdict: approve
reviewed_sha: d651caf8bf53f3c45399078bfecb5fde04dca45d
produced_by_spec_version: '1.0'
produced_at_sha: d651caf8bf53f3c45399078bfecb5fde04dca45d
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
classify() uses render()'s refusal for the refused state, returns missing when there are no markers, and otherwise compares the rendered bytes with the input, so it returns only the four closed states and never writes. The tests cover each acceptance criterion, both changed paths are inside the scope fence, and all checks passed.

## Findings
- none
