---
id: tombstone-000157
kind: tombstone
link: merge-retire-branch-check
reopen_after_days: 90
message: box-000157-e1377df3
---
The bug this message describes is already fixed by merged work. merge-retire-branch-check (merged) set the intended behaviour for a failed branch delete: re-raise only while the branch still exists, and tolerate the failure only when the branch is already gone. squatch/merge.py:428-436 does exactly that. When `branch_delete` raises a `GitError`, the code runs `rev_parse refs/heads/<stem>`. If the branch is gone, that rev_parse raises `GitError`, which is caught with `pass`, so the delete failure is tolerated. If the branch still exists, rev_parse succeeds and the `else:` branch re-raises the original delete error. The logic is not inverted. The message reads the inner try as letting rev_parse's own error out, but it misses the `except GitError: pass` / `else: raise error` structure. The rewrite it suggests (`if await branch_exists: raise`) would change only the style, not the behaviour, and no incident calls for it (`evidence: None`). Reopen if a regeneration removes the `else: raise error` or the `except GitError: pass` arm, if a retire ever reports success while `refs/heads/<stem>` still exists, or if a retire fails for a branch that is already gone.
