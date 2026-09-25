---
verdict: approve
reviewed_sha: c9922224a16f62b062ee66c464b2eabacd2d4ecd
produced_by_spec_version: '1.0'
produced_at_sha: c9922224a16f62b062ee66c464b2eabacd2d4ecd
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diff adds `squatch/reject.py` with the fixed-order routing predicate and the `awaiting` fold. The runner stamps the marker on the terminal it already writes and journals the arrival after it; the drain excludes awaiting stems, auto-keeps funded ones through the runner's verdict writer, and journals arrivals for older spent parks; `status` gains the `reject queue` section. Every acceptance criterion has a covering test, all changed paths are inside the fence, and every mechanical check passed.

## Findings
- none
