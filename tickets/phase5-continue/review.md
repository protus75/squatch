---
verdict: snag
reviewed_sha: 057db06f9b8ac7dada4009c56df35e811a5535a9
produced_by_spec_version: '1.0'
produced_at_sha: 057db06f9b8ac7dada4009c56df35e811a5535a9
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
Both tickets are well-formed and checks are green, but tests/test_seeded_phase5_01.py leaves out several contract clauses that the acceptance criteria require it to pin. The ticket text contains every one of those clauses, so each gap is a simple added assertion.

## Findings
- correctness_review at tests/test_seeded_phase5_01.py:145: Acceptance criterion 4 says the test must carry 'every later row, dependency, owner, and terminal'. It checks the rows and owners but none of the later-row edges or the terminal's tier. It never asserts that `phase5-continue-03` depends on both feature stems or that `phase5-continue-04` depends on `retro-doctor-cli`. It also never asserts that `phase5-exit` is KNOWN-HARD high/high. All three statements are in tickets/phase5-continue-02/ticket.md (lines 82, 94, 99), so a regeneration could change any of these edges or the tier and the test would stay green. (paved road: Add these strings to the Scope-in assertion list: "`phase5-continue-03` depends on both feature stems", "`phase5-continue-04` depends on `retro-doctor-cli`" and "`phase5-exit` is KNOWN-HARD high/high".)
- correctness_review at tests/test_seeded_phase5_01.py:155: Acceptance criterion 6 requires pinning 'status and baseline's direct dependencies'. The asserted string "depends directly on `scorecard-reporting` and `retro-box-activation`" covers only status-projection. Nothing asserts that `baseline-binding-reader` depends directly on `retro-box-activation`. Criterion 6 also requires the closed baseline 'fallback'. The test pins only the torn-tail/malformed REVOKED rule. It does not pin the supervised fallback for missing or empty routing, unresolved placeholders, unknown tiers or unreadable specs, 'without raising' (ticket lines 67-69). (paved road: Assert "`baseline-binding-reader` depends directly on `retro-box-activation`" and "missing or empty routing, unresolved placeholders, unknown tiers, and unreadable specs resolve to the supervised side without raising" against the flattened Scope in.)
- correctness_review at tests/test_seeded_phase5_01.py:125: Acceptance criterion 3 requires the emitted scorecard ticket to pin its 'focused test cases'. The ticket's own Scope in also names malformed-invoice exclusion as a required test case alongside input immutability. The test asserts "input immutability" but never asserts the malformed-input exclusion clause, although the scorecard ticket states it (lines 30, 53, 73). A regenerated ticket could drop the malformed-invoice test requirement and the test would still pass. (paved road: Add an assertion that the scorecard ticket's flattened Scope in contains "malformed-input exclusion". Also assert that its Acceptance criteria require `tests/test_scorecard.py` to prove malformed-input exclusion for completed check invoices.)
