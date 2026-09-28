---
verdict: snag
reviewed_sha: 112186c6281da49cb4a5f7e8a23d125aac4cf77a
produced_by_spec_version: '1.0'
produced_at_sha: 112186c6281da49cb4a5f7e8a23d125aac4cf77a
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The authored tickets and most pins match the ticket, and the sizes pinned in EXISTING_AT_AUTHORING match the base commit. The predecessor-test preservation check is only a string search, though, and does not bind a predecessor assertion that the new reliability-battery paths can break to an owner who can edit it.

## Findings
- correctness_review at tests/test_seeded_phase4_03.py:118: The ticket requires 'Preserve predecessor tests and bind invalidated assertions to their editing owner', and acceptance criterion 2 asks the test to prove predecessor-test preservation. The test only checks that tests/test_seeded_phase4_02.py contains two strings. That file's caller-closure assertion (lines 175-183) scans every tests/ and eval/ .py file for `stages.compose|compose_pipeline|compose_daemon_timers|restart_session|Serve(|Session(`. It requires every match to be inside provider-cooldown-failover's fence or PREDECESSOR. reliability-battery creates eval/reliability_battery.py and tests/test_reliability_battery.py to drive the provider/stage boundary. If either file calls one of those symbols, test_seeded_phase4_02.py goes red. reliability-battery's fence does not include that test, so the implementer cannot fix it in place. Nothing in this admission prevents this or assigns an owner. I am not certain the battery will call those symbols, but the ticket explicitly required this closure. (paved road: Mirror the phase4_02 caller-closure pattern in test_seeded_phase4_03.py. Either assert that reliability-battery's new paths are allowed to match the predecessor scan and add tests/test_seeded_phase4_02.py to reliability-battery's fence and Context as the editing owner, or have reliability-battery's Scope out forbid those constructors in its new files and pin that prohibition here. Then replace the string-presence check with an assertion that the predecessor's invariants still hold for the new-path set.)
