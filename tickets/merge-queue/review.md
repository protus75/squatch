---
verdict: snag
reviewed_sha: ca9effdf426181acf0ee324c7e7004e237523d7e
produced_by_spec_version: '1.0'
produced_at_sha: ca9effdf426181acf0ee324c7e7004e237523d7e
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The queue construction, the additive Git seams, both resolution rungs, the tree-hash assertion and the tests all meet the ticket, and the checks are green. One failure path breaks the unwind invariant: a non-conflict rebase failure that happens after git has already started the rebase returns a typed finding but leaves the candidate worktree mid-rebase.

## Findings
- correctness_review at squatch/mergequeue.py:168: `_rebase` turns every non-conflict `GitError` from `rebase_stop_at_conflict` into `CandidateRebaseFinding` without checking whether a rebase is in progress. The test only covers a dirty worktree, where git refuses to start. Git can also fail after the rebase has started without leaving any unmerged paths, for example when an untracked file would be overwritten while replaying a commit. In that case `.git/rebase-merge` exists, HEAD is detached mid-replay, and the queue returns `gate_failed` without aborting. Admission has not unwound, and the next admission of that candidate fails with 'rebase already in progress'. The paved road then asks a human to restore the worktree, which the queue should do itself. The same gap appears in two other places: an exception thrown inside the conflict loop (`conflicted_paths` raising after a failed `rebase_continue`, or a regenerate `process.run` timeout) escapes `admit` with the rebase still in progress. (paved road: After a non-conflict `GitError`, check whether a rebase is in progress (`rev-parse --git-path rebase-merge` / `rebase-apply`, or an additive `Git` query) and call `rebase_abort` if one is, before returning the typed finding. Wrap the conflict-resolution loop in try/except (or finally) so any exception aborts the in-progress rebase before it propagates. Add a test where the rebase starts, then fails without conflicted paths, and assert that the worktree ends on its branch head with no rebase state.)
