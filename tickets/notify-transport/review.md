---
verdict: snag
reviewed_sha: c895bab50c75614b98f734161423c2deb6d23522
produced_by_spec_version: '1.0'
produced_at_sha: c895bab50c75614b98f734161423c2deb6d23522
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The wiring, seam isolation, config closure, keys and replay behavior match the ticket. However, the reconciler notifies holds that are already released and tells the recipient to resume them. That makes the push message wrong on the first deploy and whenever a hold is released before the next poll.

## Findings
- correctness_review at squatch/notify.py:64: `_escalations` builds `holds` (the control_hold records not yet released, with released ones popped) but never uses it for integration_red_streak. The second loop yields every `control_hold` event with `released is False` from the whole journal, including holds that were later released. Two cases send a wrong message. (1) On the first `serve` after this lands, every past red-streak hold, all long since released, is pushed with 'After inspection: squatch resume --hold-id <id>', which points to a hold that no longer exists. (2) A hold released through the control inbox before the next watcher poll still gets pushed with a resume action. Storm trips have the same problem: a trip whose storm_trip hold was already released is left out of `storm_holds`. It is then rendered with the 'No active hold exists ... A pending trip cannot be resumed before its hold exists' action, which is false for a trip that already had a hold and was resolved. This is a logic defect (a computed release map that is ignored) that sends misleading escalations. No test covers a released hold. (paved road: Use the `holds` map for released holds. Yield integration_red_streak escalations only for `hold_id in holds`. For storm trips, skip or reword any trip whose hold was released: track released storm_trip hold trip_ids separately and do not send the 'pending trip' action for them. Add a test in tests/test_notify.py that journals a red-streak hold, then its release, then runs reconcile and asserts no transport call. Add a matching test for a storm trip whose hold was released.)
