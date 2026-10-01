---
id: tombstone-000225
kind: tombstone
link: reject-queue
reopen_after_days: 90
message: box-000225-01e5c981
---
The merged reject-queue work already has the behavior the message asks the plan to require. Its Goal says the drain 'auto-keeps it with a machine-actor `confirm` while no spine cap is spent, and otherwise holds it for the operator's `confirm`/`reject`'. The code does the same. `route` in squatch/reject.py:65-66 stamps `split`/`reject`/`abandon-human` onto the Reject queue, and a null verdict goes there too (:40-41). Then `Drain._resolve_rejects` (squatch/drain.py:387-396) checks each awaiting stem. When `spent(...)` is None it calls `signal_verdict(..., 'confirm', actor='machine', reason='auto-keep: retry budget remains')`. So a verdict-keyed arrival never parks a stem while budget remains, and only a spent cap holds it for the operator. The plan already states this rule: SQUATCH_PLAN.md:754 says 'pre-daemon default is auto-keep while retry budget remains, section 11.4', and lines 1135, 1177 and 1503 say the same. The 'before that queue exists' wording at :1179 describes a bootstrap interval that is now over, since the Reject queue and Phases 2-6 have all merged. Adding a pre-queue rule now would put change history into the plan, which section 17 rules out. The message gives no evidence and comes from `bootstrap-ingest`. Reopen if a regeneration of reject-queue drops the machine auto-keep in `_resolve_rejects`, or if a journal shows a verdict-routed stem held awaiting the operator while no spine cap is spent.
