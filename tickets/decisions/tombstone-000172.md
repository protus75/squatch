---
id: tombstone-000172
kind: tombstone
link: shakeout-reconcile
reopen_after_days: 90
message: box-000172-f79ef1be
---
Merged work already covers this. The message comes from bootstrap ingest. It describes the Phase 1 window, before the reap, when a faulted run's paved road (`squatch run <stem>`) came back in on the same run sequence and replayed its completed effect keys. It asks for a test that pins the same-sequence path so the later reap's change to a fresh sequence would show up. That reap has since landed. `Runner.session` runs `reconcile(...)` before intake and before every dispatch, so a faulted run left `running` is reaped `abandoned` on the next entry. The same-sequence re-entry the message wants pinned can no longer happen. shakeout-reconcile (merged) pins the post-reap behaviour the message calls 'the flip': an orphaned `running` with no terminal is reaped `abandoned` after harvest on the next entry, and the stem comes back with a fresh run sequence. restart-timers and worker-recovery-disposition (merged) also cover reap-before-dispatch and its recorded disposition. tombstone-000165 closed the sibling message from the same window for the same reason. A test pinning the old same-sequence behaviour would now be asserting a path that no longer exists. Reopen if a regeneration removes or moves the `reconcile` call in `Runner.session`, if `_fault` starts writing its own terminal, or if a journal shows a re-entry after a fault reusing the faulted run's `run_seq`.
