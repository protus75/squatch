---
verdict: approve
reviewed_sha: a937a71c9001ad2e81fb877a63db2254379fd4bd
produced_by_spec_version: '1.0'
produced_at_sha: a937a71c9001ad2e81fb877a63db2254379fd4bd
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
I found no defects. The harvest allowlist, the ordering in the non-ok terminal handler (harvest lift, then cap draw, then the terminal with `harvest`/`harvest_error`, then the wipe), the reconcile orphan harvest, the extension of the shared lift path, the prior-attempts render cap and prompt exclusion, and the quoting of Review diff delimiters all match the ticket. The diff stays inside the fence, spells no raw delimiter, and the check report is green.

## Findings
- none
