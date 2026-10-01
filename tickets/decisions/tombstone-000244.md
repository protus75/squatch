---
id: tombstone-000244
kind: tombstone
link: reject-queue
reopen_after_days: 90
message: box-000244-1eed02d5
---
The edge the message describes is real. tickets/reject-queue/ticket.md:13 lists `diagnosis-eval-run` under `depends`. The blocking risk it predicts is settled history, though. reject-queue is merged and appears in merged_work, so the edge never kept the queue from dispatching. diagnosis-eval-run finished in one attempt with no `attempts/` harvest. Its committed eval/reports/diagnosis-eval.json scored all 12 fixtures with `stopped: null` for about $1.27 against a $5.00 cap (decision-000235, decision-000226), so the edge never parked anything. The pieces the message says the edge would hold back (the ladder, triage, and batch 4) are merged too: reject-verbs, shakeout-ladder, and suggestion-box, and triage is producing verdicts in this same registry. Dropping the edge now, or citing a plan sentence for it, would mean regenerating a finished ticket and adding change history with no failure behind it. The message gives no evidence and comes from bootstrap-ingest, so under D10 that edit would be speculative. Reopen if reject-queue is regenerated or re-dispatched while diagnosis-eval-run is unmerged, red, or parked, or if a later plan edit makes the Phase 2 ordering between the diagnosis eval and the Reject queue explicit.
