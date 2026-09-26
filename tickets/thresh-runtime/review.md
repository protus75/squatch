---
verdict: snag
reviewed_sha: 9e908f4c7e7526535950d9c372ce2edf2f9817de
produced_by_spec_version: '1.0'
produced_at_sha: 9e908f4c7e7526535950d9c372ce2edf2f9817de
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The breaker and concurrency runtime work and are tested, but the flat-subscription threshold makes no decision: nothing in thresh.py acts on quota_exhausted or limits.quota_window_minutes. The plan (section 6) makes those the flat-subscription backstop, so the first acceptance criterion is only half met.

## Findings
- correctness_review at squatch/thresh.py:61: Acceptance mismatch. The flat-subscription threshold is only a `flat_subscription` boolean (kind == 'cli') that `decide()` never reads. It never produces an allow or hold decision. Plan section 6 names the flat-subscription backstops as the provider's own `rate_limited | quota_exhausted` limits: `quota_exhausted` marks the provider as cooling down for `limits.quota_window_minutes`. The runtime has no quota cooldown state and no hold reason for it (HoldReason is only provider_concurrency | circuit_open), and it ignores `quota_window_minutes` entirely. So 'flat-subscription ... thresholds make deterministic allow or hold decisions' is not implemented. (paved road: When `record_failure` gets a `quota_exhausted` fact, arm a per-provider cooldown until clock() + timedelta(minutes=limits.quota_window_minutes). Add a hold reason such as `quota_cooldown` and have `decide()` return it, with `retry_at` set, while the cooldown is active. Clear the cooldown at its exact expiry.)
- correctness_review at tests/test_thresh.py:41: Acceptance mismatch. The test named for flat subscription only checks that the boolean is True and then tests the concurrency cap. It never shows a flat-subscription limit producing a hold or an allow, so the first criterion's flat-subscription half has no proof. (paved road: Add a test that records a `quota_exhausted` failure and asserts that `decide()` holds with the quota reason and `retry_at` = now + quota_window_minutes. It should still hold 1 microsecond before the boundary and allow exactly at it.)
- correctness_review at squatch/providers.py:110: The FailureClass vocabulary was widened, but the provider layer can still only produce `auth_error` or `unclassified`. `quota_exhausted`, `rate_limited` and `outage` are never produced from a CLI exit, so the runtime can never receive the facts that drive the quota cooldown or an outage trip. This may be acceptable if classification signatures are deliberately left to a later ticket (I am unsure). If so, that deferral should be explicit, not silent. (paved road: Either add per-adapter signatures for quota/rate-limit exits (as auth_failure_signature does) with tests in tests/test_providers.py, or narrow the vocabulary change and state the deferral where later admission work picks it up.)
