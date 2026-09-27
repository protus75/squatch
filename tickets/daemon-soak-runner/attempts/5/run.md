## Outcome
premise_failed

## Surprises / judgment calls
The current branch is daemon-soak-runner at untouched base bc69e45c9780bd2bf8a62061bdfb70e7d95cd93b. The rejected prior implementation is absent: eval/daemon_soak.py contains only the canonical writer, and tests/test_daemon_soak_runner.py is a new deliverable, not an existing Context file.

The worker-recovery disposition is a plan/composition gap. The section 20 contract requires member-local production disposition evidence; the closed DaemonSoakEntry in squatch/artifacts.py accepts only box or alert, even for a red member. The plan's Phase 3 exit contract requires every named fault to reach one of those destinations. An abandoned terminal or an applied lifecycle kill decision is not a run-scoped alert record.

No implementation files changed and no commit was created, as required for an authoring premise failure. The run record remains uncommitted.

## Dead ends
Source trace establishes the blocker:
- squatch/daemon.py:492 kill_worker_stop_consumer aborts the active invocation and stops workers; squatch/control.py:227 writes lifecycle control_decision signals without a ticket or run_seq, not an alert/escalation.
- squatch/reconcile.py:76 reaps the orphan, harvests it, and journals abandoned. Its extract call supplies no Box. squatch/harvest.py:95 only files records when a Box is supplied; reconciliation writes no alert/escalation either.
- squatch/runner.py:334 returns immediately for a settled redispatch, before failure harvest and escalation routing. squatch/merge.py:212 finalizes successful daemon admission as merged without filing the kill fault.
Thus a clean killed/reconciled/rerun member cannot supply the required box/alert disposition and its producing_run. Planting a second verification failure, scripting an unrelated second problem, hand-filing a Box record, or relabeling control decisions as alerts would manufacture the evidence rejected by the prior review.

Paved road: repair SQUATCH_PLAN.md section 20 and authorize a production owner such as squatch/reconcile.py to record a run-scoped kill/recovery disposition, or explicitly revise the recovery evidence contract and closed schema in squatch/artifacts.py. All these paths are outside this ticket's fence. No repair was attempted inline.

Verification was run exactly as authored on the untouched base:
- uv run pytest tests/test_daemon_soak_runner.py -q: exit 4, requested new test file does not exist because implementation stopped at the premise audit.
- uv run pytest tests/test_daemon_soak.py -q: exit 0, 4 passed.
- uv run pytest -q: exit 0, 1179 passed in 51.82 seconds.
These baseline checks do not constitute soak evidence; no ordinary soak lane or committed report was produced.

## Second problems filed
None. The missing worker-recovery disposition is the blocking premise above, not an adjacent change. No pre-existing red tests were found in the full baseline suite.

## Resolved engine/model
OpenAI / GPT-6 (Codex); exact serving variant not exposed.

## Predicted vs actual
Expected: 75 minutes. Actual: approximately 5 minutes for the premise audit, baseline verification, and run record.
