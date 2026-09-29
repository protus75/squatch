---
verdict: snag
reviewed_sha: fd164c4308d3fa7cf451f1768430b23ee195287a
produced_by_spec_version: '1.0'
produced_at_sha: fd164c4308d3fa7cf451f1768430b23ee195287a
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The status projection, the additive fields, the production scorecard wiring and the malformed-metric exclusion all match the ticket, and the checks are green. One defect remains: the new test in tests/test_seeded_phase2.py is a live-size assertion that the ticket forbids, and it proves nothing about the pinned refused set.

## Findings
- correctness_review at tests/test_seeded_phase2.py:217: `test_context_refused_set_does_not_rescan_later_live_file_growth` asserts `len((REPO / 'tests/test_cli.py').read_text()) > EXISTING_AT_AUTHORING[path]`. That ties the test to the live size of another file, and the ticket says the measured sizes are 'synthetic authoring-time sizes, never live-size assertions'. The test goes red if tests/test_cli.py is ever trimmed below 15174 chars, even though nothing about the pin changed. Its second assertion, `path not in CONTEXT_REFUSED`, checks a literal frozenset, so it is always true and cannot detect a rescan. CONTEXT_REFUSED was already a pinned literal on the base commit, so this test adds only a fragile coupling. (paved road: Delete the live read. To prove the pin, assert something that fails if the refused set were computed from the live tree. For example, check that CONTEXT_REFUSED equals the expected historical literal, or that the Context-refusal test reads only CONTEXT_REFUSED and EXISTING_AT_AUTHORING and never a live file size. Keep every size in the test synthetic.)
