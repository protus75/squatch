---
verdict: snag
reviewed_sha: 62298b037750a907f6a543365862e1380c65e457
produced_by_spec_version: '1.0'
produced_at_sha: 62298b037750a907f6a543365862e1380c65e457
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
Every changed path is inside the fence, the check report is green, and each acceptance criterion has a test that meets it. One failure path is not safe to replay: a crash after the Box records a report, but before the report file is renamed to .filed, makes the same report count again as a rereport.

## Findings
- correctness_review at squatch/inbox.py:96: `_consume_one` looks up `by_origin` and calls `record_rereport(existing.id)` with no `incoming_id`. `consume` renames the report to `.filed` only after `enqueue` or `record_rereport` has returned, so a crash or `OSError` between the durable Box write and `fs.replace` leaves `*.report.json` in place. On the next pass, `by_origin` finds the message this same file created and adds one to `reports`. The same thing happens after a crash between a real rereport and its rename. `record_rereport` already has an idempotency receipt (`incoming_id`/`rereport_ids`) for this case, but the inbox does not use it. As a result, one report can be counted two or more times, which can push a tombstone over its reopen threshold and reopen it, all because of a crash-restart. I am confident the window exists; how often it happens in practice is uncertain. (paved road: Derive a stable receipt from the arrival itself, for example `sha256` of the report file bytes. Store it on the message at `enqueue` time, or pass it as `incoming_id=` to `record_rereport`. On a `by_origin` hit, skip counting when the existing message's own receipt, or its `rereport_ids`, already holds that value, then rename the file to `.filed`. Add a `tests/test_inbox.py` case that makes `fs.replace` fail once after a successful enqueue, re-runs `consume`, and asserts `reports == 1`.)
