---
id: tombstone-000268
kind: tombstone
link: decision-000266
reopen_after_days: 30
message: box-000268-216c23ff
---
decision-000266 already covers this message. Both came from watchdog-activation's run record, and both ask for the same follow-up: bind the watchdog to the author, triage and requisition roots, to standalone diagnosis, and to Serve's separate Rework driver. watchdog-activation is merged, and its Goal limits activation to the Stages-owned Driver on bootstrap drain and serve, which this message's second sentence repeats. decision-000266 recorded no ticket for three reasons. First, no incident is named: no spiral or stuck run appears in any of these roots, and D10 requires one. Second, the shipped signal is spend since the last mutation under a ticket's `## Scope fence`, and it does not fit the author, triage or requisition roots, which run without a ticket fence. Binding them would need a new signal shape, and section 9 says a new shape needs a pinned spiral fixture that the shipped signal misses. Third, diagnosis and Rework already have the per-stage `wait_for` hard timeout. This message adds no evidence (`evidence: None`) and no new root. Reopen on decision-000266's conditions: a run in any of these roots is seen busy without progress (spend with no output, or a stuck call), or a spiral fixture pinned against one of these roots shows the shipped signal missing it.
