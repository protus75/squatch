---
verdict: snag
reviewed_sha: e0df10f15dc1527b6f872478d1ff19866231c609
produced_by_spec_version: '1.0'
produced_at_sha: e0df10f15dc1527b6f872478d1ff19866231c609
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diff stays inside the fence, and the Phase 3 section-20 pinning in the predecessor tests is correct. However, tests/test_seeded_phase4_02.py does not prove predecessor-test closure (acceptance criterion 2). Its render and delimiter proofs also read live bytes that this admission's own sibling will change, which is the retroactive-failure defect this ticket fixes in the Phase 3 tests.

## Findings
- correctness_review at tests/test_seeded_phase4_02.py:130: Acceptance criterion 2 requires the test to prove predecessor-test closure. The test named for it only checks that ON_DEMAND paths are fenced and that two provider suites are Context. It never lists or checks the predecessor tests that exercise the signatures provider-cooldown-failover must migrate. Those tests are outside the fence: tests/test_watchdog.py and tests/test_kill_cli_activation.py wrap and call compose_pipeline, tests/test_storm_notification_activation.py wraps compose_daemon_timers, and tests/test_seeded_phase3_06.py pins the compose_pipeline signature text. Nothing asserts that each one is either inside the provider ticket's fence or safe from the shared-payload migration, so criterion 2 is only partly met. (paved road: Add a PREDECESSOR set naming every existing test that references stages.compose, compose_pipeline, Serve, Session, restart_session, or compose_daemon_timers. Assert that each one is either in provider-cooldown-failover's scope_fence (it owns the migration) or listed as a read-only predecessor whose access is kwargs-passthrough and preserved. Follow the pattern in test_seeded_phase4_01 and test_seeded_phase3_10's predecessor-closure tests.)
- correctness_review at tests/test_seeded_phase4_02.py:162: The headroom proof renders against the live SQUATCH_PLAN.md, so later append-only growth of section 20 will retroactively fail this historical seed. This ticket fixes exactly that defect in the Phase 3 tests. Line 138 has the same problem: it scans live bytes of Context paths that provider-cooldown-failover hooks and will edit (squatch/providers.py, squatch/timers.py, tests/test_providers.py, tests/test_restart_timers.py) for DATA_MARKER. test_seeded_phase4_01 deliberately excludes mutable paths from that scan so later sibling edits cannot turn the historical proof red. (paved road: Pin SECTION_20_CHARS_AT_AUTHORING and substitute a same-size section 20 in the render, the same way as the Phase 3 migration in this diff. Restrict the DATA_MARKER scan to Context paths not owned or hooked by any admission in OWNERSHIP, the same way as test_seeded_phase4_01's mutable_paths exclusion.)
