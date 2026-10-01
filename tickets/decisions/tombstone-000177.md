---
id: tombstone-000177
kind: tombstone
link: spine-harvest
reopen_after_days: 90
message: box-000177-06ca1934
---
Merged work already pins the order. spine-harvest (merged) made 'harvest -> journal -> wipe' the contract for both the terminal handler and the orphan reap, and the reconcile test now enforces it. In tests/test_reconcile.py:111-153, test_an_orphaned_running_is_reaped_abandoned_and_its_worktree_removed_on_the_next_run patches Git.worktree_remove with an observer. At the moment of the wipe, that observer asserts the worktree still exists and takes a snapshot of the journal. The test then looks for the `abandoned` state_transition in that snapshot with next(...), and asserts the recovery_alert comes right after it (alert_index == terminal_index + 1). If the journal write and the wipe in reconcile (squatch/reconcile.py:99-111) were swapped, the snapshot would hold no `abandoned` event, next() would raise StopIteration, and the test would fail. The mutation the message describes is therefore caught today. The message comes from the Phase 1 bootstrap ingest window, before harvest landed and before this observer assertion existed. A second test with a raising worktree_remove would prove the same order a second time, so it is not needed (D10). Reopen if a regeneration removes the removal-time journal snapshot from that test, or if reconcile is found to wipe an orphan's worktree before its `abandoned` terminal is on disk.
