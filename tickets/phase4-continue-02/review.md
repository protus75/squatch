---
verdict: snag
reviewed_sha: 7192373413f11765b1760730ccf90d9d1c14e0ac
produced_by_spec_version: '1.0'
produced_at_sha: 7192373413f11765b1760730ccf90d9d1c14e0ac
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The authored tickets, the ownership pins, the finite suffix and the Phase 3 render pins all hold, and every check is green. However, the delimiter-bearing Context exclusion that the acceptance criteria require is never actually checked for provider-cooldown-failover.

## Findings
- correctness_review at tests/test_seeded_phase4_02.py:159: The second acceptance criterion requires the test to prove that no Context contains the prompt delimiter. The loop `for path in set(ticket.context) - mutable_paths: assert DATA_MARKER not in ...` skips every path in the ownership owns/hooks. All four provider-cooldown-failover Context paths (squatch/providers.py, squatch/timers.py, tests/test_providers.py, tests/test_restart_timers.py) are in its hooks, so the check runs on nothing for that ticket. It only covers phase4-continue-03's single Context file. The files do not contain '<<<squatch:' today, but the test would not catch it if they did. Also, the assert that PREDECESSOR equals the same literal it was defined from is a no-op and adds nothing to the predecessor-closure proof. (paved road: Check DATA_MARKER against every Context path of each seed, mutable or not, since Context is rendered at dispatch time either way. If mutable paths must be excluded, pin their authoring-time content hash or size and check the marker against that pinned content. Replace the self-equality assert on PREDECESSOR with a check against something outside the test, such as the predecessor paths actually affected by the provider fence.)
