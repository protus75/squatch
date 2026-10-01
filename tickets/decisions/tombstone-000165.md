---
id: tombstone-000165
kind: tombstone
link: shakeout-reconcile
reopen_after_days: 90
message: box-000165-a9f29672
---
Merged work already covers this. The message comes from bootstrap ingest and describes a window that has since closed: before reconcile-on-entry existed, a faulted run left behind as `running` made the next `run <stem>` reuse the same run sequence and replay that run's completed effect keys. Reconcile-on-entry has now landed. `Runner.session` (squatch/runner.py:170-192) goes lock, then journal, then `reconcile(...)` at :187, then intake, and it does this before every dispatch, so an orphaned `running` is reaped as `abandoned` before the next run starts. `_fault` (:494-501) still writes no terminal, and its docstring and paved road hand the orphan to reconcile in the same way. Three merged tickets deliver and pin the behavior. shakeout-reconcile tests that the next entry reaps the orphan `abandoned` after harvesting it and that the stem comes back with a fresh run sequence. restart-timers reaps interrupted work before dispatch. worker-recovery-disposition records the abandon. So the same-sequence replay the message describes can no longer happen, and the paved road's wording is accurate as it stands. Reopen if a regeneration removes the `reconcile` call from `Runner.session` or moves it after dispatch, if `_fault` starts writing its own terminal, or if a journal shows a re-entry after a fault reusing the faulted run's `run_seq`.
