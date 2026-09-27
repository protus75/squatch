## Outcome
ok

## Surprises / judgment calls
The worktree started from the dormant boundary, not attempt 10's implementation. Reused the seven scoped files from d28b54fd01169145f73df9845863b178f724b519, inspected their diff, and corrected the two remaining review findings. Section 20 already specifies decision-before-mutation and retrying accepted work; these were implementation defects, not plan defects.

Direct control now checks its own decision and refuses stale resumes with a paved road. Both publication and application output identify the actual hold. Lifecycle recovery preserves accepted-but-unapplied decisions so a crash before hold creation cannot lose an accepted pause. Regression coverage exercises this crash window through the production factory, successful resume output, wrong and previously released hold refusals, and live publication labels.

Verification passed exactly as specified: focused command, 113 passed in 9.97s; full `uv run pytest -q`, 1018 passed in 45.85s. Preservation-only suites remain unchanged. Only the seven fenced code/test paths were committed; this run record remains uncommitted.

## Dead ends
None.

## Second problems filed
None.

## Resolved engine/model
OpenAI / GPT-6 (Codex); exact serving variant unavailable.

## Predicted vs actual
Expected: 75 minutes. Actual: approximately 8 minutes, including inspection, recovery of the prior implementation, fixes, verification, and commit.
