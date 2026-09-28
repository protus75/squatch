---
verdict: snag
reviewed_sha: e8f59787207bbdb20eb8e1d404a7287e70d73db1
produced_by_spec_version: '1.0'
produced_at_sha: e8f59787207bbdb20eb8e1d404a7287e70d73db1
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The new phase4_02 seed test and the phase4_01 ownership update meet the ticket. The pinned section-20 sizes added to the three Phase 3 historical render checks are wrong, though: each is far below the real size of section 20 at its authoring commit, so the historical headroom proofs are weakened instead of pinned.

## Findings
- correctness_review at tests/test_seeded_phase3_01.py:33: SECTION_20_CHARS_AT_AUTHORING = 7000, but section 20 ('## 20.' up to '## 21.') in SQUATCH_PLAN.md at authoring commit 64b1f83 is 8911 chars (the file is pure ASCII, and offsets 362948 to 371859 are measured the same way the test slices it). The comment calling this the plan slice at authoring time is false. It swaps a smaller synthetic section into the max-effort render, so the check passes under a bound the real authoring-time render never had to meet. The acceptance criterion asks for pinned authoring-time section-20 sizes. (paved road: Pin the measured value 8911, the length of section 20 at 64b1f83 counted from '## 20.' to the start of '## 21.', and keep the render assertion. If the render then breaks the headroom limit, report that as a finding. Do not round the size down.)
- correctness_review at tests/test_seeded_phase3_08.py:55: SECTION_20_CHARS_AT_AUTHORING = 7700, but section 20 at authoring commit d4961ff is 11661 chars (offsets 362948 to 374609). That understates it by about 34%, so the historical render proof does not test the authoring-time plan. (paved road: Pin 11661, the measured length of section 20 at d4961ff, and fix the comment to match.)
- correctness_review at tests/test_seeded_phase3_10.py:58: SECTION_20_CHARS_AT_AUTHORING = 8500, but section 20 at authoring commit 4fe624e is 12826 chars (offsets 362948 to 375774). That understates it by about 34%, so the historical render proof does not test the authoring-time plan. (paved road: Pin 12826, the measured length of section 20 at 4fe624e, and fix the comment to match.)
