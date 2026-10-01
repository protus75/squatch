---
id: decision-000263
kind: decision
link: box-000263-1819c135
reopen_after_days: 30
message: box-000263-1819c135
---
No ticket: the report is stale. It was filed at phase3-exit, where verification attribution found this test red at the merge base too and excused it. On main the test now expects `squatch/artifacts.py` in the phase3-continue-23 exit Context, which is exactly the omission the report names. The committed phase3-continue-23 ticket lists that path in its Context block and says its own deliverable migrates this test to include it. phase3-continue-23, phase3-exit and every later phase through phase6-exit are merged, so no admitted seed's dispatch depends on this assertion. A tombstone does not fit: decision-000260 and its tombstones cover section-20 render-headroom drift, not a Context-partition omission, and no rendered Goal names this repair. Two things are unconfirmed. The test was not re-run green in this session because execution was not approved. The exact commit that added the path was also not isolated: the test file's history shows a201b18 (phase3-continue-23 authoring) and then cf476cb ('fix(plan): close retro and doctor CLI contract'). Reopen if this test is red on main, if a verification-attribution report names it again, or if phase3-continue-23 or phase3-exit is regenerated.

Evidence: tests/test_seeded_phase3_22.py:157-162 asserts the phase3-continue-23 exit Context as (tickets/soak-run/daemon-soak-report.json, squatch/artifacts.py, eval/daemon_soak.py, tests/test_daemon_soak_runner.py, tests/test_seeded_phase3_11.py). tickets/phase3-continue-23/ticket.md:54 lists squatch/artifacts.py in Context, and :86 says this test migrates to include it. The test file's history is a201b18 then cf476cb. phase3-continue-23 and phase3-exit are both in merged_work. The test was not run.
