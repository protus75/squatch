---
id: tombstone-000218
kind: tombstone
link: reject-queue
reopen_after_days: 90
message: box-000218-834584c1
---
Merged reject-queue work already covers this, including the retrofit onto the drain's spent-cap park path. On every scan, `Drain._resolve_rejects` (squatch/drain.py:387-405, called at :234) walks every parked stem. When a stem has a spent spine cap (`spent(...)` at :390) and no unresolved Reject-queue arrival yet (`stem not in facts.rejects`), it journals the releasable arrival: a `signal` with `escalation: ARRIVAL`, the spent-cap reason, and the terminal's `run_seq` (:398-403). Its docstring says it exists to 'Materialize legacy spent arrivals'. So a stem parked at a spent `infra` or `diagnosis` cap before the queue landed still gets an arrival record for the queue projection to key on (`Fold.rejects`, :109). The `_tail` report then lists it with the `confirm`/`reject` verbs (:495-500). The re-offer path also skips stems that are already in `facts.rejects` or have a spent cap (:372-374), so none is re-dispatched without a record. Reopen if a regeneration of reject-queue drops the legacy-arrival materialization in `_resolve_rejects`, or if a journal shows a stem parked at a spent spine cap with no Reject-queue arrival after a drain scan.
