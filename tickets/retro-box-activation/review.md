---
verdict: snag
reviewed_sha: c64687e6468a1168be4b8595ad8505932b5fdade
produced_by_spec_version: '1.0'
produced_at_sha: c64687e6468a1168be4b8595ad8505932b5fdade
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diff mostly matches the ticket, but two failure paths are wrong. The Author bridge is written after the ticket commit, so a failure or crash can leave a committed retro ticket with no provenance bridge. The tombstone reopen persists the incremented count before the journal callback, so its signal key is not stable on replay.

## Findings
- correctness_review at squatch/author.py:223: `_record_retro_bridge` runs only after `intake.commit` has already committed the authored ticket. If the bridge append raises, the handler reports the failure and returns None without discarding the ticket, and the Box message stays pending. The result is an orphan committed `box:retro_finding` ticket with no `retro-ticket/<stem>` bridge. Merge then returns the `retro_provenance` hard finding for it on every run, so the ticket is held with no release path, and retrying the message authors a duplicate ticket. A crash between the commit and the append leaves the same state. (paved road: Append the idempotent bridge signal before `intake.commit`. Its same-key, same-body check already makes a retry safe. Then a committed retro ticket always has its bridge, and a failed commit leaves only a harmless bridge that the next attempt reuses.)
- correctness_review at squatch/box.py:241: `record_rereport` writes the incremented `reports` to disk before it calls the rereport callback. If the callback raises, or the process crashes between the write and the journal append, the record stays tombstoned with reports=3. The next arrival raises it to 4 and journals `tombstone-reopen/<box_id>/4`. The ticket requires the exact K=3 key, so the signal is not replay-stable. The `>=` threshold also reopens a re-tombstoned record on its very next arrival without a fresh K=3 count. The no-callback path has the same problem: every later ingest keeps counting past 3, so a journal-backed rerun journals a key other than /3. (paved road: Compute the post-increment message, call the callback, and only then persist both the count and the reopen in one `_replace`. Alternatively, trigger the reopen at exactly the threshold crossing, so a retried arrival reuses the same `tombstone-reopen/<box_id>/3` key through the callback's existing idempotent same-body check. Add a test in `tests/test_retro_box.py` where the callback raises once and a retry journals exactly `/3`.)
