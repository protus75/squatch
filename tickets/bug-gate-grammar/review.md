---
verdict: approve
reviewed_sha: def2397ea3039bd14439192062deee95c5c46933
produced_by_spec_version: '1.0'
produced_at_sha: def2397ea3039bd14439192062deee95c5c46933
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diff adds the BugEvidence hard gate to the Check set and hardens `carries` prefixes to repo-relative form. The gate requires the `## Regression` command to pass at branch head and fail at merge base with the `carries` overlay, and it refuses any branch-added or changed test file that is not carried, so a test missing at base is never accepted as evidence. tests/test_bug_gate.py covers all three acceptance criteria, every changed path is inside the fence, and the check report is green.

## Findings
- none
