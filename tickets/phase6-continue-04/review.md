---
verdict: snag
reviewed_sha: 1ab39037596609959cd11481cd5805d2a1930083
produced_by_spec_version: '1.0'
produced_at_sha: 1ab39037596609959cd11481cd5805d2a1930083
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The test pins the escape-column identity, edges, tier, fence, partition, the remaining suffix contracts, terminal custody and the max-effort renders. However, it checks the escape-column contract phrases against the commissioning ticket phase6-continue-04 instead of the authored escape-column ticket, so the escape row's contract is never actually pinned.

## Findings
- correctness_review at tests/test_seeded_phase6_04.py:81: `scope = _scope("phase6-continue-04")` reads the Scope-in of the ticket that commissioned this diff, not the authored `tickets/escape-column/ticket.md`. The phrase assertions that follow (app_commit source, first-parent HEAD ancestry, one valid trailer pair, immutable (signature,ticket), count-once, exclusions, mergequeue allowlist-only) therefore check text that is already fixed and prove nothing about the escape-column seed. A regenerated escape-column ticket could drop or change any of these contract terms and this test would still pass. That defeats the acceptance criterion 'pins the escape row' and the Definition of rejected 'changed contracts'. The precedent `tests/test_seeded_phase6_03.py` (lines 101-103) asserts contract phrases against each payload's own `_scope(stem)`. (paved road: Assert the phrases against `_scope("escape-column")`, matching the phase6_03 CONTRACTS pattern. Every listed phrase appears verbatim in the committed escape-column Scope in, so the change is a one-token swap. Optionally keep a separate check that phase6-continue-04 still carries them.)
