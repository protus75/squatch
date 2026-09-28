---
verdict: snag
reviewed_sha: aab138665d9120d0fc4c6541d82592f6c03673d7
produced_by_spec_version: '1.0'
produced_at_sha: aab138665d9120d0fc4c6541d82592f6c03673d7
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
Schema registration and fence are correct. The report is still not fully execution-derived: the auditor verdict is hardcoded green, produced_at_sha is the repo directory name instead of a commit SHA, and 'cooldown=armed' is asserted without reading any cooldown state.

## Findings
- correctness_review at eval/reliability_battery.py:136: Every entry is built with auditor="green" as a literal. The battery grades itself: `green` then only compares two strings the battery also wrote, and nothing independent audits the evidence journal. The ticket forbids self-attestation. The sibling batteries (eval/daemon_soak.py:542, eval/shakeout/__main__.py:87) set `auditor = "red" if audit_journal(...) else "green"`. (paved road: Set auditor per member from `audit_journal(root / member)` after the journal closes, the same way daemon_soak/shakeout do. Add a test that a corrupted or empty member journal yields auditor="red" and green=False.)
- correctness_review at eval/reliability_battery.py:153: produced_at_sha=Path(repo).resolve().name puts the checkout's directory basename (e.g. 'squatch') in the SHA field, so the report is not tied to the commit that produced it. The test at tests/test_reliability_battery.py:43 passes Path("base") and asserts produced_at_sha == "base", which locks the wrong behavior in. (paved road: Resolve HEAD through the git wrapper with the injected process seam, as eval/daemon_soak.py:565 does (`Git(process, ...).rev_parse(repo, "HEAD")`). Update the test to inject a process that returns a known SHA and assert that SHA.)
- correctness_review at eval/reliability_battery.py:131: For classified_quota_exhaustion, observed is the literal "quota_exhausted;cooldown=armed" whenever failure_class == "quota_exhausted". The code never checks that a cooldown was actually armed (runtime/Registry cooldown state or the journal's cooldown event). Acceptance criterion 2 requires each member to be derived from merged boundary evidence, and this half of the string is assumed, not observed. (paved road: Read the cooldown state from the ProviderRuntime, or the cooldown timer/journal event, after the call, and build the `cooldown=` part from what was actually recorded (e.g. provider name and expiry). Add a test where no cooldown is armed and show the member goes red.)
- correctness_review at eval/reliability_battery.py:120: The all-candidates-cooling check uses a bare `assert error.failure_class == "quota_exhausted"`, which disappears under python -O. If the third call does not raise, nothing records it, so the 'all candidates cooling' precondition is never proven in the evidence and can pass silently. The first two calls also swallow ProviderError without checking its class. (paved road: Put the class of the all-cooling error into `observed` (e.g. `all_cooling={error.failure_class}`), and make a missing error produce a mismatching observed value instead of passing.)
