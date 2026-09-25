---
verdict: snag
reviewed_sha: 97e08cc4a02eda414310cf94088dcfe88c78e6db
produced_by_spec_version: '1.0'
produced_at_sha: 97e08cc4a02eda414310cf94088dcfe88c78e6db
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diff stays inside the fence, the check report is green, and the existing tests plus the two new ones pin all nine observables. Three shakeout members need fixing first: they call git through raw subprocess, the secret member passes when git itself fails, and the timeout member never checks where the marker appears in the prompt.

## Findings
- correctness_review at eval/shakeout/stages_group.py:118: The fake implementer's `_write` action runs `git add` and `git commit` through raw `subprocess.run`, and `_run_secret_not_persisted` does the same for `git grep` at line 293. This breaks the engine rule that all git goes through `squatch/git.py` and external binaries run only through argv wrapper modules. Before this change, `eval/` had no raw `subprocess` use: `Bench.commit` already goes through `self.git` (`Git` over `SubprocessExec`). (paved road: Commit through the bench's `Git` wrapper (the action runs inside the async `call`, so await `git.add`/`git.commit` there, or use `Bench.commit` on the worktree). Do the committed-content search with the wrapper or by reading `git show`/`ls-tree` output through it. Drop the `subprocess` import.)
- correctness_review at eval/shakeout/stages_group.py:293: The `git grep -l <secret> HEAD -- tickets/<stem>` call ignores the exit code and treats empty stdout as proof that no committed file carries the secret. If git fails (exit 128: bad revision, bad pathspec, wrong cwd or env), stdout is also empty, so the member reports `secret:redacted_everywhere` without checking anything. A redaction check should fail closed. (paved road: Treat only exit 1 (no match) as absent, exit 0 as a leak, and any other code as a member failure. A better fix is to list the committed files under `tickets/<stem>/` through the git wrapper and check each blob's bytes for the secret.)
- correctness_review at eval/shakeout/stages_group.py:271: The ticket says the `timeout_dead_ends` observable is attempt two's prompt carrying the marker INSIDE the prior-attempts block. The member only checks `prompt.count(marker) == 1`, so a render that put the dead ends in any other block would still pass. The `reject_reentry` member and the new unit test do check position, between `prior_attempts` and `context`. (paved road: Add the same check `reject_reentry` uses: `prompt.index('[squatch-data:data name="prior_attempts"') < prompt.index(marker) < prompt.index('[squatch-data:data name="context"')`, and require it before returning `timeout:dead_ends_rendered`.)
