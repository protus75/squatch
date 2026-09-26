---
verdict: snag
reviewed_sha: d1d3bc013c04908226d2a19b40e51d608d2bfe97
produced_by_spec_version: '1.0'
produced_at_sha: d1d3bc013c04908226d2a19b40e51d608d2bfe97
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
Decisions are journaled before mutation, crash replay is sound, and stale-lifecycle and pre-hold releases are handled. However, a request that was already fully consumed calls the governed mutation again when the same request is republished, so consumption is not exactly once. The test that covers this path hides the repeat call.

## Findings
- correctness_review at squatch/control.py:126: The journal records an accepted decision but never records that the mutation finished. So when `existing.outcome == "accepted"` and the lifecycle matches, the code calls `_apply` / `mutate` again. It cannot tell a crash leftover from a republication of a request that was already completed and removed. Repro: publish request R, `consume` (accepted, mutated, file removed), `publish_control` R again (allowed, because the file is gone), `consume`: `mutate` runs a second time. `test_release_is_bound_to_one_never_reused_hold_instance` does exactly this, but it asserts only the `applied` set, which hides `calls == 2`. This conflicts with the ticket's 'consumption is exactly once' requirement and with the acceptance criterion that tests prove exactly-once consumption. Uncertainty: if the plan intends at-least-once delivery with an idempotency key, this may be by design. The comment in the code says as much, but the ticket does not. (paved road: After `mutate` returns, journal a completion marker for the request, for example a `control_decision` projection with an `applied` flag, or a second keyed signal under `control/<request_id>`. Only retry `_apply` when the request is accepted and no completion marker exists; once the marker exists, remove the file without calling `mutate`. Change the release and republish tests to assert `mutation.calls == 1`. Keep the retry-after-crash test (`calls == 2`) for the one boundary the journal cannot close, between `mutate` returning and the marker being appended.)
