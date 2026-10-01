---
id: tombstone-000160
kind: tombstone
link: merge-queue
reopen_after_days: 30
message: box-000160-f659be0c
---
Merged work already covers this. The message comes from bootstrap ingest and describes the Phase 1/2 inline admission, which journaled no conflict facts and left Phase 3 to do it. merge-queue (merged) built the serial MergeQueue 'with its conflict facts and two typed resolution rungs'. squatch/mergequeue.py:43-46 defines `ConflictFacts` (stem, conflicted `paths`, `rung` none|mechanical|rework). `_record` (:330-335) journals it as a `merge_conflict_facts` signal keyed `merge_conflict_facts/<stem>/<run_seq>`, and every exit of an admission calls it: clean, mechanical rung, rework handoff, refused rebase, and integration red (:181-225). merge-queue-activation and serve-merge-admission (merged) send production Serve deliveries through that queue. The squatch/merge.py docstring (:15-16) already says daemon admission hands rebase through integration to the MergeQueue. Plan section 18 (SQUATCH_PLAN.md:1259) says conflict facts are journaled from Phase 3 onward. That is the daemon path, so the bootstrap inline path journaling none matches the plan and is not a gap. Writing a deferral note into the merge.py docstring would describe a deferral that has already been delivered. Reopen if a regeneration removes `_record` from any MergeQueue admission exit, if Serve admission stops going through the MergeQueue, or if the operator changes section 9 to require conflict facts on the bootstrap inline admission.
