---
verdict: snag
reviewed_sha: 0255a58f6d33ca8301297731ccdd311c0eb93ce3
produced_by_spec_version: '1.0'
produced_at_sha: 0255a58f6d33ca8301297731ccdd311c0eb93ce3
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
Daemon admission sends settled deliveries through the composed MergeQueue and leaves bootstrap inline, but a rung-2 conflict returns the outcome `rework` to the runner. `rework` is not in the closed Outcome vocabulary, so production Serve dispatch faults on it.

## Findings
- correctness_review at squatch/merge.py:229: `admit_daemon` returns `Admission(queued.outcome, ...)` whenever the queue does not report `integrated`, so a rung-2 unresolved conflict comes back as outcome `rework`. `Pipeline.run` copies that into `Delivery.outcome`. The runner checks it against `OUTCOMES` in `squatch/runner.py:326`, which is taken from `artifacts.Outcome` (ok, already_satisfied, invalid_artifact, gate_failed, premise_failed, timeout, infra_error, budget_exceeded) and has no `rework`. The runner raises TypeError and turns it into a `_fault`. In production, every conflict that reaches the Rework rung becomes an engine fault instead of a clean non-merged terminal with the branch kept for post-unwind Rework. The new tests call `pipeline.run` directly and never go through the runner, so they miss this. (paved road: Map the queue's `rework` result onto a vocabulary outcome that leaves the branch in place and does not retire (for example `gate_failed` with a typed conflict finding taken from `queued.conflict_facts`). Do not extend the vocabulary outside the fence. Add a test that sends a rung-2 conflict through the runner/Serve dispatch path, not only `Pipeline.run`.)
- correctness_review at tests/test_mergequeue.py: The `rework` case asserts `result.outcome == "rework"`. That pins a Delivery outcome the runner rejects, so the test locks in the defect above instead of catching it. The acceptance criterion needs daemon-mode conflict handling to reach both rungs through production dispatch, and a result that faults in the runner does not meet it. (paved road: Once the mapping is fixed, assert the outcome is in `squatch.artifacts.OUTCOMES`, the branch and worktree are intact, and the handoff is published only after the slot unwinds.)
