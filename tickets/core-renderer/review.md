---
verdict: snag
reviewed_sha: 20429638d28701433990d764bc35f148df373f3c
produced_by_spec_version: '1.0'
produced_at_sha: 20429638d28701433990d764bc35f148df373f3c
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The renderer's logic is sound: it inserts on first adoption, refuses marker-like corruption, and a second render is byte-identical. It fails on two points: its marker grammar contradicts the plan's host contract, and the no-Git acceptance criterion is not really proven.

## Findings
- correctness_review at squatch/hostfiles.py:10: The plan's section 15 host contract names the managed block `<!-- squatch:core begin/end -->`. The renderer emits and parses `<!-- squatch:core start ... -->` instead. Section 8 says the block carries a version and hash stamp, which the start line correctly includes, but the opening keyword must be `begin`. The drift classifier (`core-drift-classifier`), the `core_drift` gate, and the seed CLAUDE.md adoption all build on this grammar. Merging `start` bakes a non-spec marker into every host file and makes a future rename a breaking marker migration. If the plan's `begin` is wrong, that is a plan defect to fix in the plan first, not something to diverge from here. (paved road: Change the start marker to `<!-- squatch:core begin version=N sha256=<hex> -->` in `_START` and `managed_block`, and update the refusal fixtures in tests/test_hostfiles.py to match. If `start` is the intended spelling, fix SQUATCH_PLAN.md section 15 first and regenerate from it.)
- correctness_review at tests/test_hostfiles.py:43: `test_rendering_has_no_git_or_commit_effect` only monkeypatches `subprocess.run`. Engine Git goes through `squatch/git.py` over the async process-exec seam, not `subprocess.run`. A renderer that imported and called `squatch.git` would still pass this test, so it does not prove the acceptance criterion 'rendering performs no Git operation or commit'. The test also never checks that the renderer writes nothing to disk. (paved road: Make the test fail on any Git path the engine actually uses. For example, assert that `squatch.hostfiles` does not import `squatch.git`, `subprocess`, or the process/filesystem seams (inspect the module's globals or AST). Alternatively, monkeypatch `squatch.git`'s entry points and the process seam to raise, and render inside a `tmp_path` checkout, asserting that no file changed and that `git status`/HEAD are unchanged.)
