## Outcome
premise_failed

## Surprises / judgment calls
The required production merge-queue route is absent on base commit 649f541144056205e9ae5749fd5b9dcf26551205, on branch daemon-soak-runner. No implementation files were changed and no commit was made. The ticket explicitly requires stopping when a forced change is outside its fence.

Plan status: section 20 requires production composition evidence and explicitly parks concrete missing production seams for plan repair. Its prerequisite that the merged serve composition can exercise both conflict-resolution rungs is not satisfied by this tree.

## Dead ends
Traced the actual path before coding: Serve.compose's work callback calls Runner.dispatch (squatch/serve.py), Runner.dispatch calls pipeline.run (squatch/runner.py:322), and Pipeline.run calls self.merge.admit (squatch/merge.py:370). compose_pipeline constructs both a Merge and a separate merge queue, then returns Pipeline(stages, merge, queue); it does not route settled deliveries into that queue.

Merge.admit calls its own _rebase, which uses Git.rebase and aborts conflicts. It never invokes MergeQueue.admit or the queue's conflict-resolution rungs. The serve rework worker only consumes queue.next_rework; it supplies no admission route. Consequently, advancing main through the Git/process seams cannot make this production flow exercise conflict_resolution_rungs. The separate queue integration-check adapter is likewise not reached by settled deliveries.

Required repair owner: squatch/merge.py, outside all three Scope fence prefixes and explicitly excluded by Scope out. Repair the production admission routing under a separately authorized plan/ticket change, then rerun this ticket. Calling queue.admit from the harness, replacing the production pipeline, or manufacturing approval/event/Box evidence would reproduce the rejected prior approach.

Verification commands were not run: this is a source-proven missing production route, not a test regression or an already_satisfied claim. Stopped before implementing tests or a runner, as required by the fence rule. The requested new tests/test_daemon_soak_runner.py does not exist on the untouched base.

## Second problems filed
None separate from the blocking production-admission defect above.

## Resolved engine/model
OpenAI / GPT-6 (Codex); exact serving model variant not exposed.

## Predicted vs actual
Expected: 75 minutes. Actual: approximately 4 minutes of read-only contract and production-path inspection, followed by this run record; no soak was run.
