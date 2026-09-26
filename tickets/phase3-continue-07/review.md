---
verdict: snag
reviewed_sha: 798f7eef19f4051759409c02d8b7fbe5f07a65b0
produced_by_spec_version: '1.0'
produced_at_sha: 798f7eef19f4051759409c02d8b7fbe5f07a65b0
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The seeds and pinned sizes are correct, but the test does not prove two things the acceptance criteria require: the Verification commands, and the continuation's pause-pair edges, tiers, budgets and cap. The phase3-continue-08 seed also leaves out the exact pause-pair dependency edges that this ticket requires it to carry.

## Findings
- correctness_review at tests/test_seeded_phase3_07.py:120: Acceptance criterion 3 requires proof that control-inbox runs tests/test_daemon_tasks.py in Verification. It also requires proof that both deliverables run tests/test_daemon_composition.py in Verification. The test only checks that the Scope in prose contains "`tests/test_daemon_composition.py`" and "run it". It never reads the `## Verification` section. A seed whose Verification block dropped either command would still pass. (paved road: Parse `_section(stem, "Verification")` for each deliverable and assert that the pytest argv includes tests/test_daemon_composition.py. For control-inbox, also assert it includes tests/test_daemon_tasks.py.)
- correctness_review at tests/test_seeded_phase3_07.py:125: Acceptance criterion 5 requires the test to show that phase3-continue-08 carries the exact pause-pair edges, tier/effort, budgets, cap and fences. The test checks only pause_ownership, the predecessor names, the suffix and two headroom/size-map phrases. It never checks the edges (dispatch-pause-boundary depends on phase3-continue-08; pause-resume-activation depends on dispatch-pause-boundary; phase3-continue-09 depends on both), medium/medium, 75m/150m, the seeding cap, or fences derived as owns followed by hooks. The authored tickets/phase3-continue-08/ticket.md also says only "exact dependency edges" and never names them, even though this ticket requires the continuation to pin them explicitly. (paved road: State the three concrete dependency edges in the phase3-continue-08 Scope in, along with medium/medium, 75m/150m and seeding cap 3. Add assertions for each edge, the tier/effort, the budgets and the cap to test_continuation_pins_pause_closure_and_shrinking_suffix. Also assert that each pause seed's fence is its owns followed by its hooks.)
