---
verdict: snag
reviewed_sha: 04348c29d7a0f117bbe67a9f28349ebbb0c9d527
produced_by_spec_version: '1.0'
produced_at_sha: 04348c29d7a0f117bbe67a9f28349ebbb0c9d527
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
Base-diff attribution is wired correctly through Check, the merge regate, checks.json, and Box dedup, and every changed path is inside the fence. Two things need fixing: the fail-closed messages write raw exception text into persistent findings without redacting it, and one test_stages.py acceptance clause (no leftover base worktree on disk or in `git worktree list`) is only proven with a fake git.

## Findings
- correctness_review at squatch/stages.py:333: The three 'base attribution failed' branches (lines 321, 333, 343) put `str(e)` straight into the Finding message. For a GitError that string includes git's captured stderr (`GitError.__init__` adds `stderr.strip()`). The Finding is written to the journal (which does not redact), the engine log event, and the committed `checks.json`, and none of these is scrubbed at that point: this file's comment says output is 'Scrubbed once at receipt'. That makes it a captured stream reaching persistent sinks without redaction. merge.py already handles git stderr on the rebase-conflict path by passing it through `self._redact(...)`. I rate the chance of a configured secret actually appearing here as low, but the sink is not redacted. (paved road: Pass the exception text through `self._redact(f"{type(e).__name__}: {e}")` before interpolating it, ideally in one helper shared by all three fail-closed branches, and add a test assertion that a secret in a raised GitError's stderr comes out as the redaction token.)
- correctness_review at tests/test_stages.py:461: The acceptance criterion requires tests/test_stages.py to show that 'after every check no `<stem>-base-` worktree remains on disk or in `git worktree list`'. The new attribution tests use a fake `AttributionGit` and only assert `added == removed`. `test_red_verification_fails_the_check` is the one stages test that creates a real base worktree through the real Git (branch red, base green), and it asserts neither the disk nor the registry. The only on-disk and registry check is in tests/test_terminal.py, so this test_stages.py criterion is only partly met. I'm not certain whether the criterion meant to accept the fake-git proxy. (paved road: In `test_red_verification_fails_the_check`, and in any other real-git stages test that reaches a base run, assert that `(repo / h.config.worktree_root).glob(f"{STEM}-base-*")` is empty and that `f"{STEM}-base-"` does not appear in `git worktree list`.)
