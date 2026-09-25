## Outcome
ok

## Surprises / judgment calls
The corrected ticket fences the git wrapper and its test. I reused the prior green implementation, renamed its `common_dir` method to the contract's exact `git_common_dir` API, and added direct seam plus real main/worktree resolution tests. The instance state already contained all 257 bootstrap suggestions from the prior idempotent ingestion, so I preserved those records and committed the required source-file deletion without duplicating them.

## Dead ends
The two prior attempts stopped on a scope-fence omission; the re-authored ticket resolved it. No implementation dead end remained in this attempt.

## Second problems filed

## Resolved engine/model
OpenAI Codex / GPT-5 / implement spec 1.1

## Predicted vs actual
Expected 90m; actual approximately 20m, including base verification, prior-diff audit, correction, and the full verification pass.
