---
id: decision-000264
kind: decision
link: box-000264-472225d7
reopen_after_days: 30
message: box-000264-472225d7
---
No ticket: the report is stale. The test raises ValueError only when `_phase4_registry()` (tests/test_seeded_phase3_23.py:90-93) cannot find one of its two plan anchors. On HEAD (833e548) both anchors are in SQUATCH_PLAN.md in the order the test needs: `Phase 4 boundary registry (DECIDED):` appears once (line 1557), and `` `phase3-continue-23` fences `` appears after it (line 1614). The report was filed at phase3-exit, where verification attribution excused this red as a base failure. Since then the test file was last changed in fbd9867 ('fix(plan): specify phase 5 status and baseline contracts'), after the authoring commit a201b18. phase3-continue-23, phase3-exit and every later phase through phase6-exit are merged, so no admitted seed's dispatch depends on this assertion. A tombstone does not fit. decision-000263 covers a different assertion in this file (the `squatch/artifacts.py` exit Context), and decision-000260 covers section-20 render-headroom drift, not a missing registry anchor. Two things are unconfirmed: the test was not re-run in this session, and I could not isolate the commit that restored or re-anchored the sentinel because `git log -S` was not approved.

Evidence: SQUATCH_PLAN.md:1557 contains `Phase 4 boundary registry (DECIDED):` (count 1). SQUATCH_PLAN.md:1614 is `` `phase3-continue-23` fences: ... ``, which follows the registry start, so both `str.index` calls in tests/test_seeded_phase3_23.py:92-93 resolve on HEAD. Test-file history: a201b18, then fbd9867. Reopen if this test is red on main, if a verification-attribution report names it again with a traceback, or if section 19/20 prose holding either anchor is edited or regenerated.
