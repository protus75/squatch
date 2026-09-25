---
verdict: snag
reviewed_sha: 2d9b5bccfa77731ae52e9e4848423dbb5aa69a9a
produced_by_spec_version: '1.0'
produced_at_sha: 2d9b5bccfa77731ae52e9e4848423dbb5aa69a9a
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The harvest, terminal, and wipe handling is sound and stays inside the scope fence, but two things fall short of the ticket. The harvest part of the prior-attempts render is not held to HARVEST_RENDER_CHARS, and no test in tests/test_terminal.py checks that the harvest lift commit is journaled before the terminal state_transition.

## Findings
- correctness_review at squatch/stages.py:598: `_prior_attempts` applies the HARVEST_RENDER_CHARS budget only to `detail_text` (via `remaining`). `summary_text` has no limit: it holds one line per earlier attempt, and each line embeds that attempt's whole `diff_stat` joined onto one line. A ticket with many attempts, or one whose diff touches many files, therefore produces a harvest contribution larger than HARVEST_RENDER_CHARS. The ticket requires 'the whole harvest contribution capped at HARVEST_RENDER_CHARS'. (paved road: Truncate the joined harvest text (summaries plus details) to HARVEST_RENDER_CHARS, or cap summary_text first and give details what is left. Add a test with an oversized diff_stat or many attempts that asserts the harvest contribution is at most HARVEST_RENDER_CHARS.)
- correctness_review at tests/test_terminal.py:193: Acceptance criterion 3 requires that for a non-ok run the journal order is the harvest lift's ticket-plane commit, then the terminal `state_transition`. The changed tests check the transition bodies (`harvest` path), the worktree wipe, and that the branch survives. None of them checks where the `lift/<stem>/<n>/harvest` effect sits in the journal relative to the terminal transition. (paved road: In the non-ok terminal test, read `d.events()`. Find the index of the `effect_completion` whose key is the harvest lift key (and whose result carries a commit sha), and assert it comes before the index of the terminal `state_transition`.)
