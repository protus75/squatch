---
verdict: snag
reviewed_sha: 0c2e952a725d012cae96c6ad4b74c3bb45b487b6
produced_by_spec_version: '1.0'
produced_at_sha: 0c2e952a725d012cae96c6ad4b74c3bb45b487b6
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The grammar, the carries overlay and the three acceptance tests are sound and inside the fence, but the `carries` coverage check counts deleted paths, so any bug fix that deletes or renames a test file is rejected and cannot fix the ticket to get past the gate.

## Findings
- correctness_review at squatch/stages.py:540: `changed` comes from `git diff --name-only base...branch`, which also lists files the branch DELETED. A deleted test or fixture path (for example the old name of a renamed `tests/test_x.py`) passes `_is_test_path`, so it lands in `uncovered`. `carried` is built from `ls_files(workspace)`, which cannot contain a deleted path, so no `carries:` prefix can ever cover it. The gate then fails with a paved road the implementer cannot follow. That breaks the fail-closed-with-paved-road rule, and the tests never exercise a deletion. (paved road: Before computing `uncovered`, drop changed paths that are not present in the branch workspace (for example, intersect with the `ls_files(workspace)` result you already fetch in `_carried_paths`). Add a `tests/test_bug_gate.py` case where the branch deletes or renames a test file and the gate still passes when the new path is carried.)
