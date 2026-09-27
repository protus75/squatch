---
verdict: snag
reviewed_sha: 58c7b459a0628fc7aa3501e0521a51983227309c
produced_by_spec_version: '1.0'
produced_at_sha: 58c7b459a0628fc7aa3501e0521a51983227309c
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The release path matches the merge.py emitter shape, binds box status, link, merge and typed rerun correctly, and has the required refusal tests. One gap remains: after a release, the same report/test/fix identity can be quarantined and released a second time, which the idempotency criterion forbids.

## Findings
- correctness_review at squatch/flake.py:105: Releasing the same identity twice is only a no-op while nothing new is detected. Release removes the entry from the fold, so a later `Flake.detect(test_id, signature, box_id)` for the same report finds no entry and appends a fresh `flake/<box_id>` event, putting the test back in quarantine. A later `release` for the same box_id and fix_stem then passes every check again: the box is still `authored` with the same link, the old `merged` transition is still in the journal, and the caller supplies a green rerun. That appends a second `signal` with the identical key `flake-release/<box_id>/<fix_stem>`. The criterion says a second release of the same identity appends no event and changes no state. It also means a test that flakes again after its fix merged is released immediately on the old fix's evidence. The idempotency test only covers release-then-release with no re-detection in between. I am moderately confident this is reachable once detection is activated, because detect keys by box_id and the report stays `authored`. (paved road: Make the release identity terminal inside flake.py. Have `release` return False when an event with key `flake-release/<box_id>/<fix_stem>` already exists in the journal. Alternatively, have `_fold_quarantine`/`detect` refuse to re-quarantine a box_id that already has a release. Add a test in tests/test_flake.py that runs release, then re-detect, then release again, and asserts no second release event is appended, including after reconstruction.)
