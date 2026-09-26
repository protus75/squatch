---
verdict: snag
reviewed_sha: e213ec822fd6a0d4a654bd8c3dc20f39cab0ec72
produced_by_spec_version: '1.0'
produced_at_sha: e213ec822fd6a0d4a654bd8c3dc20f39cab0ec72
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The inbox, seam and daemon hook meet every acceptance criterion, stay inside the scope fence, and the check report is green. One logic defect remains: `_consume` deletes a reused request_id file without reading it or journaling anything when the id already has a terminal non-accepted decision, so no conflict is recorded.

## Findings
- correctness_review at squatch/control.py:95: `_consume` checks `decisions.get(path.stem)` first. If the stored outcome is anything other than `accepted` (stale, invalid or conflict), it removes the file and returns the old decision without reading or validating the new content. Example: request R is journaled `stale`. A new file R.json with a different action or lifecycle then arrives. It is deleted with no journal record and treated as the earlier decision. The `existing.request != request` conflict check only runs for ids previously decided `accepted`. Result: a control request is consumed without any journaled decision, and the conflict outcome is applied inconsistently depending on the earlier outcome. (Moderate confidence: I think this is a real gap, but it only fires when a request_id is reused.) (paved road: Remove the pre-read short-circuit. Read and validate the file first, then run the `existing.request != request` conflict check for every previously decided id, not just accepted ones. Only for an identical re-publication of a terminal non-accepted request, remove the file and return the existing decision. For an invalid-then-republished stem whose earlier decision has `request=None`, treat valid new content as a conflict. Add a test to `tests/test_control.py` that publishes a different request under a request_id already decided `stale` and asserts a `conflict` decision is journaled and nothing is mutated.)
