---
id: tombstone-000261
kind: tombstone
link: decision-000260
reopen_after_days: 30
message: box-000261-34c3e80b
---
decision-000260 already covers this report. Its class, origin and repair are the same; only the test file differs. This report was also filed at phase3-exit. There, verification attribution found the test red at the merge base too and excused it. The cause is the live-file drift that decision-000260 describes: the test rendered the dispatch-pause-boundary seed against the live SQUATCH_PLAN.md, and section 20 kept growing after the seed was authored, which pushed the render past the 120000-character headroom limit. Commit 2eaa0a6 (phase4-continue-02, which is in merged_work) is the same repair decision-000260 cites, and it also changed tests/test_seeded_phase3_08.py, the last commit to touch that file. The file now defines `SECTION_20_CHARS_AT_AUTHORING = 11661` (line 54), and `_authoring_plan()` (line 88) swaps section 20 for a placeholder of that size. `test_successor_is_shrinking_and_synthetic_renders_fit_headroom` renders against that pinned plan (line 205), alongside the `EXISTING_AT_AUTHORING` Context sizes that were already pinned. dispatch-pause-boundary, phase3-continue-08 and every later phase through phase6-exit are merged, so no admitted seed's dispatch depends on this measurement. As with decision-000260, the test was not re-run green in this session. Reopen if this test is red on main after 2eaa0a6, if a verification-attribution report names it again, or if specs/implement.md or Spec.render grows enough to push the pinned render past the limit.
