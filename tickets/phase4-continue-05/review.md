---
verdict: snag
reviewed_sha: fe81de12f2d145bc4f147d444e2fd6ff7899d476
produced_by_spec_version: '1.0'
produced_at_sha: fe81de12f2d145bc4f147d444e2fd6ff7899d476
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diff stays inside the fence and the check report is green. Acceptance criterion 4 is only partly met: the test never rejects the obsolete section-19 report name or members, and it checks the three report members only as loose substrings instead of pinning section 20's exact closed order.

## Findings
- correctness_review at tests/test_seeded_phase4_05.py:98: Acceptance criterion 4 requires proving that 'no obsolete report name/member ... is admitted'. Section 20 (SQUATCH_PLAN.md:1561) names the superseded artifact `reliability-report.json` and the retired four-scenario wording, including the spiral-notification and hard-timeout scenarios. No assertion in this file rejects that obsolete name or any obsolete member in the phase4-exit ticket. A regenerated ticket that also read `tickets/reliability-run/reliability-report.json`, or that listed a spiral or hard-timeout member, would still pass. (paved road: Add negative assertions over the phase4-exit ticket text (Scope in and Context): `reliability-report.json` is absent, and no member token outside REPORT_MEMBERS appears where members are listed. For example, extract every backticked snake_case token in the member-order sentence and assert the extracted tuple equals REPORT_MEMBERS.)
- correctness_review at tests/test_seeded_phase4_05.py:99: `all(f"`{member}`" in scope for member in REPORT_MEMBERS)` only checks that each member appears somewhere. It does not pin the 'exact three-member' read that criterion 4 and section 20's 'complete closed member order' require. A reordered list, or one with a fourth member added, still passes. (paved road: Assert the exact ordered sentence from the ticket, e.g. "member order is\n`classified_quota_exhaustion`, `all_candidates_cooling_recovery`, and\n`unclassified_failure_preservation`" in scope. Or parse the member tokens in order and assert tuple equality with REPORT_MEMBERS.)
- correctness_review at tests/test_seeded_phase4_05.py:136: The three-seed cap required by criterion 3 is a hardcoded `len(row) <= 3`. It is not bound to the configured cap, while predecessor test_seeded_phase4_04.py pins `config.seeding.max_seeds_per_admission == 3`. The Phase 5 core row returned by `_admissions(STEM)` is also never checked against the cap. This is a weaker proof than the established pattern the ticket says to follow; flagged with moderate confidence because the literal 3 currently matches config. (paved road: Load the config as the first test does. Assert `config.seeding.max_seeds_per_admission == 3`, and assert that every row in FULL and in `_admissions(STEM)` has `len(row) <= config.seeding.max_seeds_per_admission`.)
