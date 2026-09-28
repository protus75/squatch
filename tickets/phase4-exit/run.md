## Outcome
premise_failed

## Surprises / judgment calls
The ticket says the section 20 integration-fence repair is complete, but the
current plan and merged production tree prove that premise false.

## Dead ends
Section 20 says the `retro_ticket_authored` journal bridge is the sole
provenance lookup because `Merge` never receives or constructs a Box. Merged
`squatch/merge.py:176` constructs a production `Box`, and `_regate` passes it
to `Verification` for base-failure filing. The same section requires every
production Box constructor to receive the rereport callback, but the complete
activation fence omits the production constructor at `squatch/status.py:119`.
It also says reopening occurs on the K-th hit without defining K in section 20;
the shipped K=3 value exists only in section 12, which the authored activation
ticket is forbidden to cite. Repairing these contradictions requires editing
`SQUATCH_PLAN.md`, outside this ticket's `tickets` and test-only scope fence.

## Second problems filed

## Resolved engine/model
OpenAI Codex / GPT-5

## Predicted vs actual
Expected 75m; actual approximately 8m before the blocking premise was proven.
