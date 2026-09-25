---
verdict: snag
reviewed_sha: ff821a5619c1fb88b400ef7d267a975ac9fc660b
produced_by_spec_version: '1.0'
produced_at_sha: ff821a5619c1fb88b400ef7d267a975ac9fc660b
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The terminal handler order, the soft-failure handling, the setup-death short-circuit, reconcile harvesting, the shared lift path and the Review delimiter quoting all match the ticket, and the checks pass. Two defects remain: the diff stat leaves out uncommitted new files, and harvested text can break the next attempt's prompt render.

## Findings
- correctness_review at squatch/git.py:71: `diff_stat` runs `git diff --stat <base>`, which leaves out untracked files. The ticket requires the stat to include uncommitted changes. A failing run often ends with the implementer having created files it never committed or staged. For that run, `harvest.json`'s `diff_stat` will not list those files, and the re-entry line 'files changed' will not either. The only test edits a file git already tracks, so it does not catch this. (paved road: Add the untracked names to the stat through a second argv wrapper, for example `git ls-files --others --exclude-standard` listed as new files, or build the stat from `git status --porcelain` together with `diff --stat`. Keep it to names and counts, never content. Add a test in `tests/test_harvest.py` where the dying worktree holds a new uncommitted file and assert that its name appears in `diff_stat`.)
- correctness_review at squatch/stages.py:588: `_prior_attempts` copies the latest `run.md` and the non-prompt spool tails (the `NNN-response.md` model replies) into the `prior_attempts` DataBlock without quoting. If either text contains the engine delimiter `DATA_MARKER`, `Spec.render` raises `RenderRefused('delimiter')`. That makes the next attempt's Implement end `premise_failed` without ever calling the model, so a whole attempt is wasted. This is likely in this repo: a Review reply or run record that quotes a delimiter-bearing diff would contain it. I am confident the render refusal happens. I am less sure how often it would come up in practice. (paved road: At the same stage-owned boundary, quote the harvest contribution the same way Review's diff is quoted: `harvest_text.replace(DATA_MARKER, "[squatch-data:")` before it joins `lines`. Leave `harvest.json` and `run.md` byte-exact. Add a test in `tests/test_drain_reentry.py` whose harvested `run.md` contains a delimiter built at runtime, and assert that the second attempt reaches the model.)
