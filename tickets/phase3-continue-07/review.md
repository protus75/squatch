---
verdict: snag
reviewed_sha: 7f1b1900ae2eaddb0d5b10d963a736494c72b9bb
produced_by_spec_version: '1.0'
produced_at_sha: 7f1b1900ae2eaddb0d5b10d963a736494c72b9bb
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The seeded test is green and matches the ticket's identities, edges, budgets, fences, Context map, size registry, pause ownership, render bound and suffix. It does not pin the exception-propagation contract or the per-consumer independent lifetime tests, both of which AC4 requires.

## Findings
- correctness_review at tests/test_seeded_phase3_07.py:137: AC4 requires the test to pin exception propagation and independently observable task lifetimes for background-consumers. The phrase tuple only checks 'clean shutdown', 'cancellation' and 'sibling cleanup'. Nothing asserts that the seed requires the owner's shutdown await to re-raise the callback's exception after cancelling and awaiting its siblings. Nothing asserts that the seed requires one independently named test per consumer lifetime. The seed's Scope in text does contain 'then re-raises that exception' and 'Test each consumer lifetime independently', so a regenerated seed could drop either requirement and this test would still pass. The seed's own acceptance criteria also never mention the re-raise. (paved road: Add phrase assertions for the re-raise contract (for example 're-raises that exception') and for per-consumer independent lifetime testing (for example 'each consumer lifetime independently') against the background-consumers Scope in. Also make the background-consumers seed's acceptance criteria name the re-raise, and assert that criterion in the test.)
