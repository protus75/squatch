---
id: tombstone-000236
kind: tombstone
link: spine-diagnosis
reopen_after_days: 30
message: box-000236-b136f91d
---
spine-diagnosis is merged, and the Fold extension the message wanted named in its Scope was built. `drain.Fold` now has `terminals: Mapping[str, Mapping]`, which holds the latest terminal body for each stem (squatch/drain.py:107). `_draw_retry` (squatch/drain.py:410-427) reads `facts.terminals[stem]['diagnosis']` and adds the verdict and each `lesson:` to the re-offer report line. The fence review accepted this change, and the work merged, so the drift the message warned about did not happen. Its rendered Goal covers the lessons-fed re-offer. Editing the seed's Scope now would only add change history, with no failure behind it. The message gives no evidence and comes from bootstrap-ingest, so under D10 that edit would be speculative. Reopen if spine-diagnosis is regenerated and its fence review flags the Fold/terminals extension or the `_draw_retry` report change as out-of-scope drift.
