## Outcome
premise_failed

## Surprises / judgment calls
The pinned producer/notification fences are feasible. The drafted producer defined a state-directory-checked ContextVar binding resolved at Box.enqueue call time, scoped by a daemon wrapper around the existing Runner session. The drafted activation wrapped _RestartRunner.session, reaching independently constructed Box instances and post-pipeline harvest without modifying runner/stages/merge/triage/author. Drain/run reaches runner/stages/merge; triage reaches triage/author through the same wrapper. Real RequisitionReview approved both revised seeds.

The requested continuation exposed a separate plan-level contradiction at SQUATCH_PLAN.md section 20. Production stage-selective dispatch suppression needs the live selection/composition owners squatch/drain.py and squatch/__main__.py, beyond the listed storm/control/daemon hold ownership. Embedding those owners with the required predecessor tests and production-composition preservation Context exceeds the 120,000-character requisition headroom. The ticket/plan permit no storm on-demand exceptions. Making the hold dormant instead leaves the finite registry without an activation owner before phase3-exit. The final requisition review returned rma on that deferral, naming SQUATCH_PLAN.md.

SQUATCH_PLAN.md is outside this ticket's Scope fence. No plan or contract was changed. No implementation commit was made. Removed this attempt's undeliverable three seed drafts and test file; preserved only this run record and requisition-validation.json as uncommitted evidence.

## Dead ends
The first authoring pass required real production hold activation within the storm/control/daemon fence; RequisitionReview rejected the missing drain/CLI closure and render partition. A second pass interpreted section 20's construction rule as allowing dormant hold construction; review rejected that because the finite suffix has no production activation owner. Neither adding an admission nor adding a storm Context exception is authorized here. Paved road: repair section 20 with explicit storm-dispatch-hold production ownership and a feasible render/Context partition, or explicitly name an activation owner and repair the finite suffix; then re-author this continuation.

Producer review also exposed expired-backlog and storage-namespace ambiguity, and notification review corrected the triage/author CLI reachability claim. Both were addressed in the discarded drafts and approved on the final live review. Some initial provider replies were malformed Markdown/prose and the real review driver retried them; the final results were schema-valid.

Validation before discarding the undeliverable drafts: uv run pytest tests/test_seeded_phase3_16.py -q exited 0 (8 passed); uv run pytest -q exited 0 (1117 passed, 50.22 seconds). All three ticket lint checks passed; every Context path was present on the untouched base. Final max-effort render sizes were 115942, 116053 and 96433 characters against 120000 headroom. Final live requisition verdicts: producer approve, notification approve, continuation rma. Passing pytest does not resolve the plan-level feasibility defect.

## Second problems filed

## Resolved engine/model
Implementer: OpenAI Codex, GPT-6 family; exact serving variant is not exposed. Requisition validation: configured claude/opus through RequisitionReview and CliClient.

## Predicted vs actual
Expected 75 minutes; actual approximately 18 minutes, including two live requisition passes and two full pytest runs. Stopped at the out-of-fence plan repair instead of committing an infeasible continuation.
