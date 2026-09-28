---
verdict: snag
reviewed_sha: b83af7ac498073b5d290ab3015cf6dc4c1e7674e
produced_by_spec_version: '1.0'
produced_at_sha: b83af7ac498073b5d290ab3015cf6dc4c1e7674e
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The detector meets nearly every criterion: strict >3x USD accounting, one flat-estimate charge per invocation, every named time boundary with stuck taking precedence, one soft trip per ticket/run_seq, dormancy kept, and the check report is green. One fail-open remains in the mutation fence check: paths are not normalized, so a path that climbs out of the fence with '..' still resets spend.

## Findings
- correctness_review at squatch/watchdog.py:96: observe_mutation compares PurePath(path).parts against the fence prefixes without collapsing '..' components. So observe_mutation('squatch/../README.md') gives parts ('squatch', '..', 'README.md'), matches the fence prefix ('squatch',), returns True and zeroes accumulated spend, even though the path resolves outside the Scope fence. The ticket requires a reset only for a path matching a fence prefix on component boundaries. Letting a path climb out of the fence is fail-open for the only thing that resets the spiral signal. Uncertainty: the later activation may only ever feed paths without '..' (for example, from git), but this construction does not enforce that. (paved road: Fail closed on paths that are not normalized and relative: reject (return False without resetting) any mutation path or fence entry that is absolute or contains a '..' or '.' component, or normalize both with posixpath.normpath before comparing parts. Add a test that asserts not subject.observe_mutation('squatch/../README.md') and that spend is unchanged.)
