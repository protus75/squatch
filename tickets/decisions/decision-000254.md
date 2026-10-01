---
id: decision-000254
kind: decision
link: box-000254-8debaf90
reopen_after_days: 90
message: box-000254-8debaf90
---
No ticket. The message asks that a deliverable's run record mention that batch 4 edited two earlier seeds in place: it added Context entries to `spine-caps` and `spine-diagnosis` so they would pass the fence-read closure test. That annotation is no longer needed. Both seeds are in merged_work, and so is the batch 4 work: suggestion-box, reject-verbs, reject-queue, the requisition-review trio and every shakeout group. Phase 2 and every later phase through phase6-exit are closed. The in-place edits went through conductor authoring, so the full seed history is already in git, and plan section 17 says provenance belongs in git history, the journal and the Suggestion Box rather than in spec or ticket prose. This box message now records the scope note too. The run record has already been written. Going back to annotate a finished deliverable, or regenerating it to add the note, would add change history with no failure behind it. The message has no evidence and comes from bootstrap-ingest, so under D10 that work would be speculative. A tombstone doesn't fit, because no rendered Goal or decision covers how a run record should note seed edits made outside a batch's scope. Reopen if batch 4, spine-caps or spine-diagnosis is regenerated and its fence review flags the Context additions as out of scope, or if a future batch has to edit an already-merged seed to satisfy a new closure test.

Evidence: spine-caps, spine-diagnosis, suggestion-box, reject-verbs, reject-queue, requisition-review-call/author/seed, all shakeout groups and phase2-exit through phase6-exit are in merged_work. Message origin is bootstrap-ingest with evidence None. Section 17 places provenance in git history, the journal and the Suggestion Box. Related bootstrap-ingest dispositions for finished seeds: tombstone-000243/000244/000246/000248, decision-000253.
