---
verdict: snag
reviewed_sha: c457616ab2af147ae81c36b5d16e353c4e6c8cb9
produced_by_spec_version: '1.0'
produced_at_sha: c457616ab2af147ae81c36b5d16e353c4e6c8cb9
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The seeds, Context partition, successor suffix and render-headroom pins meet the ticket. One problem: the registry-owner test compares against the live tree instead of authoring-time history, so it will go red when the successor tickets land their owned files.

## Findings
- correctness_review at tests/test_seeded_phase3_17.py:126: `assert not (REPO / path).exists()` runs for every NEW_PATH_OWNERS entry, including tests/test_storm_hold.py, tests/test_seeded_phase3_18.py, squatch/checkpoint.py and tests/test_checkpoint.py. storm-dispatch-hold must create tests/test_storm_hold.py, and its Verification runs `uv run pytest -q`. So this test fails as soon as the hold is implemented. The hold ticket cannot fix that, because tests/test_seeded_phase3_17.py is outside its fence. The same thing happens to phase3-continue-18 and checkpoint-push. This is the historical-versus-live comparison the ticket forbids, and none of the established seeded tests (test_seeded_phase3_10 through _16) checks that a new path is absent. (paved road: Delete the live non-existence assertion. Pin registry owners only against ticket and ownership data: each new path is in its owner's `owns`, and new paths are disjoint from Context. If authoring-time absence has to be recorded, pin it as a static constant, as EXISTING_AT_AUTHORING does, and never read the filesystem for it.)
