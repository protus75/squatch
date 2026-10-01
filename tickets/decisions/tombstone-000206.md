---
id: tombstone-000206
kind: tombstone
link: reject-verbs
reopen_after_days: 90
message: box-000206-c8047ed4
---
This was already fixed by merged work. The message comes from the bootstrap-ingest window and describes a gap from before the cap existed: it says `premise_bounce` would only arrive later with the Phase 2 ladder. The merged ticket reject-verbs added that cap and made every `premise_failed` terminal draw from it. The current code confirms this. `PREMISE_BOUNCE_CAP` is part of `SPINE_CAPS` (squatch/caps.py:14, :27) and is configured as `caps.premise_bounce` with a default of 2 (squatch/config.py:143). The terminal handler draws that cap on every `premise_failed` outcome (squatch/runner.py:442-444). `Drain._released` (squatch/drain.py:361-362) only lets an edited premise-parked stem dispatch while `remaining(..., PREMISE_BOUNCE_CAP) > 0`. Once the cap is spent, the parked report names the spent cap (drain.py:509-513). So a premise park, edit and re-run cycle is now capped by `premise_bounce`, not only by how many times the operator edits the ticket. The release is not missing its cap draw: the draw happens at the terminal, and the release checks the remaining budget. tombstone-000190 already cites this same `_released` budget check. Reopen if a later regeneration removes the `premise_bounce` draw from the `premise_failed` terminal, or removes the budget check from `_released`.
