---
id: tombstone-000257
kind: tombstone
link: decision-000253
reopen_after_days: 180
message: box-000257-173cd52b
---
decision-000253 already settled how this fixture works: `EXISTING_AT_AUTHORING` byte counts and `CONTEXT_REFUSED` in tests/test_seeded_phase2.py are deliberately pinned historical material. They exist so that later edits cannot change whether an already-admitted Phase 2 seed could be rendered. The 105,371 pin for `bootstrap/suggestions.md` (line 75) is a record of that snapshot. It was never meant to describe the commit's final tree. The file is also in `CONTEXT_REFUSED` (line 102), so its size never feeds a render-bound check: the size loop skips refused entries (lines 201-213). That means the stale count has no effect on any check. suggestion-box has merged and deleted `bootstrap/suggestions.md`, so no live file is left for the pin to drift against. Phase 2 and every later phase through phase6-exit are closed. Dropping or re-pinning the entry now would mean changing a closed phase's pinned fixture with no failure behind it. That is change history, and since the message comes from bootstrap-ingest with no evidence, the change would be speculative under D10. Reopen if the Phase 2 seed fixture is regenerated, if a refused entry's pinned size is ever found to feed a render-bound assertion, or if a later seed test pins a file that its own deliverable edits and that file is Context-eligible.
