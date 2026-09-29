---
verdict: snag
reviewed_sha: 0b93706a65b65e12f863a079a2e5ffc21331f1b4
produced_by_spec_version: '1.0'
produced_at_sha: 0b93706a65b65e12f863a079a2e5ffc21331f1b4
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diff stays inside the fence and the checks are green, but the test does not pin the row-1 on-demand partition against the authored tickets, and several remaining-row Context partitions are pinned only by generic phrases.

## Findings
- correctness_review at tests/test_seeded_phase6_01.py:52: Acceptance criterion 1 requires the test to pin row 1's Context/on-demand partitions. `ON_DEMAND` is only used in `set(CONTEXT[...]).isdisjoint(ON_DEMAND[...])`, which compares two constants inside the test and never reads `tickets/core-drift-activation/ticket.md` or `tickets/migrate-config/ticket.md`. If an authored ticket dropped or added a measured on-demand exception (for example, left `squatch/providers.py` out of the exception list), or failed to cover the whole fence with Context plus on-demand, this test would still pass. (paved road: Check each on-demand path against the authored ticket's Scope in text, for example by requiring every `ON_DEMAND[stem]` path to appear in the sentence that contains 'measured on-demand'. Also assert that `set(CONTEXT[stem]) | set(ON_DEMAND[stem])` equals `set(FENCES[stem])` for `core-drift-activation` and `migrate-config`, and that the two sets do not overlap.)
- correctness_review at tests/test_seeded_phase6_01.py:89: Acceptance criterion 2 requires the test to pin each remaining row's exact Context/on-demand partition, but several partitions are checked only with generic phrases that do not say which paths belong where. `go-grade-machinery` checks only for `"are Context"`. `escape-column` checks `"may be measured on-demand exceptions"` and `"Context"` but never ties `squatch/git.py` and `tests/test_git.py` to on-demand, or `squatch/scorecard.py` and `tests/test_scorecard.py` to Context. `exit-receipt-machinery` checks `"embedded Context"` without naming `squatch/artifacts.py` and `tests/test_gates.py`. A row-2 ticket that moved a path from Context to on-demand, or the reverse, would still pass. I am reasonably but not fully certain this falls short of the 'exact' partition the criterion asks for. (paved road: For each remaining payload, store explicit Context and on-demand path tuples, as the row-1 `CONTEXT` and `ON_DEMAND` constants do. Assert that each path appears in the segment's Context or on-demand clause, for example by locating the sentence that contains 'Context' or 'on-demand' and checking the backticked paths in it, instead of checking only for the word 'Context'.)
