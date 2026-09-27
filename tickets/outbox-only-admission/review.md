---
verdict: snag
reviewed_sha: af9bbfa658f51d6ba1ca789a1c0b7689ba1c0cb9
produced_by_spec_version: '1.0'
produced_at_sha: af9bbfa658f51d6ba1ca789a1c0b7689ba1c0cb9
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diff meets all four acceptance criteria and stays inside the fence. It has one fail-open hole: the worktree cleanliness guard does not check the source path of a rename, so an uncommitted edit outside the OUTBOX can still be exempted. It also changes the seed-lift path in the daemon integration check, which the ticket did not ask for and no test covers.

## Findings
- correctness_review at squatch/stages.py:131: output_lift_allows_empty checks only `entry.path.split(" -> ")[-1]`, which is the rename destination. With a staged rename such as `R  squatch/foo.py -> tickets/<stem>/foo.json` in the worktree, the destination is inside the OUTBOX and the guard returns True. That exempts an uncommitted deletion of `squatch/foo.py`, which is outside the OUTBOX. The ticket says: "Never exempt an uncommitted edit outside the ticket's own OUTBOX". The ticket's definition of rejected also lists "uncommitted code exemption". (paved road: Require every side of the porcelain entry to sit under the OUTBOX: `all(part.startswith(outbox) for entry in status for part in entry.path.split(" -> "))`. Add a test in tests/test_stages.py that stages a rename from a code path into `tickets/<stem>/` next to a registered report and asserts the result is still `gate_failed` with 'no committed diff'.)
- correctness_review at squatch/merge.py:482: integration_check now also passes `merge._seed_lift(...) is not None` into allow_empty. Before this diff, the daemon integration check never allowed an empty diff for seed lifts. That changes seed-lift admission behavior, which this ticket did not ask for, and no test in the diff covers it. This folds a second problem into this change; it is not needed to admit OUTBOX-only output. I am unsure whether the old behavior was a live bug, so I am flagging this for a decision rather than as a confirmed defect. (paved road: Limit integration_check to `allow_empty=lifted_output` and file the seed-lift/integration_check mismatch in the Suggestion Box as its own ticket. Or, if it is kept, add a tests/test_merge.py case proving a seed-only delivery clears the daemon integration check.)
