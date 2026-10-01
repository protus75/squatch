---
id: tombstone-000184
kind: tombstone
link: reject-verbs
reopen_after_days: 30
message: box-000184-c28aa03f
---
Merged work already covers this. The message comes from the Phase 1 bootstrap ingest. It says the retry fold had no operator-keep bound and that a stem whose cap was spent had no release inside the engine, because the `confirm <stem>` keep was deferred to Phase 2. reject-verbs (merged) delivered both pieces. It added `squatch confirm <stem>` as the keep verb, which re-enqueues the stem and re-arms its spent spine caps, and it bounds the cap fold by the operator's latest keep. The current code confirms this. In `fold` in squatch/caps.py:40-47, an operator-actor `confirm` signal resets that stem's per-cap counts, so draws made before the latest keep no longer count. `_after_keep` in squatch/ladder.py:45-55 applies the same bound to the retry-rung history. The drain fold at squatch/drain.py:137-139 tracks operator confirms. The drain's hold road at squatch/drain.py:500 names `squatch confirm <stem>` to keep, noting that it re-arms spent caps, so the report now names a verb instead of a manual touchpoint. reject-queue (merged) routes a spent-cap stem to the Reject queue, where that verb releases it. The hold and its release are both shipped, so the gap the message describes is closed. Reopen if a regeneration removes the operator-keep reset from the cap fold or the ladder fold, or if the drain's spent-cap hold stops naming `squatch confirm <stem>` as its release.
