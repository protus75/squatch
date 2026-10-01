---
id: tombstone-000252
kind: tombstone
link: shakeout-report
reopen_after_days: 180
message: box-000252-86fae203
---
The custody path this message describes has already worked for every shakeout group. shakeout-report and all eight groups (tickets, stages, driver, reconcile, merge, providers, drain, ladder) are merged, and each group's `shakeout-report.json` is on main under `tickets/<group>/`. Those files arrived through the run-record lift, which carries the worktree outbox (`_lift(stem, run_seq, "run-record", worktree=worktree)`, squatch/stages.py:677). The checks lift does not carry it (squatch/stages.py:704; the message's :432 citation is stale). So the double gate compared the bytes that were lifted, and nothing went wrong. shakeout-ladder's committed cumulative copy is the one the Phase 2 exit read, and phase2-exit has merged. Phase 2 and every later phase through phase6-exit are closed. Stating this assumption in the shakeout-report seed now would mean regenerating finished work, and changing the checks lift to carry the outbox would add a second outbox lift path with no failure behind it. Section 17 counts the first as change history in spec prose. The message gives no evidence and comes from bootstrap-ingest, so under D10 either change would be speculative. Reopen if shakeout-report or any shakeout group is regenerated or re-dispatched, if a committed `shakeout-report.json` is ever found to differ from what its group's Check-time run produced, or if the run-record lift stops carrying the worktree outbox.
