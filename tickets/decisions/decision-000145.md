---
id: decision-000145
kind: decision
link: box-000145-33641a65
reopen_after_days: 90
message: box-000145-33641a65
---
No ticket: the message is out of date. The stale refusal it describes is no longer in the tree. squatch/runner.py has no `production_pipeline` and no refusal saying the Implement/Check/Review stages have not landed. A search of the engine and tests for `production_pipeline`, 'Implement/Check/Review' and 'not landed' finds only the test name `test_lock_holder_shares_streak_across_production_pipeline_factories`. The runner now takes an injected `PipelineFactory` (runner.py:150, :157) and calls `pipeline.run` and `pipeline.diagnose` (:368-369, :446). The merge deliverable the message expected has landed: `compose_pipeline` in squatch/merge.py:550-568 builds `stages.compose` together with `Merge` behind the seam, which is what the message says prompt 7 should replace the refusal with. Merged work builds on that composition (merge-queue-activation, serve-merge-admission, scheduler-activation, serve-activation), and Phases 2 through 6 ran tickets through it. There is nothing left to fix. I did not use a tombstone because no rendered stem matches the bootstrap prompt-7 deliverable closely enough. merge-queue-activation exposes the queue inside an already-composed pipeline; it is not the change that replaced the refusal.

Evidence: squatch/runner.py: no `production_pipeline` symbol and no 'not landed' refusal text; it has a `PipelineFactory` seam at :150/:157/:368. squatch/merge.py:550-568 `compose_pipeline` calls `compose(...)` from squatch/stages.py:1210 and builds `Merge`. The only `production_pipeline` match in the repo is the test name in tests/test_daemon_composition.py:48. The message's evidence field is None. Reopen if a regeneration brings back a stage-not-landed refusal in runner.py or splits `compose_pipeline`.
