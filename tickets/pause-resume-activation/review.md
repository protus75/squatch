---
verdict: snag
reviewed_sha: d28b54fd01169145f73df9845863b178f724b519
produced_by_spec_version: '1.0'
produced_at_sha: d28b54fd01169145f73df9845863b178f724b519
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The CLI-to-inbox activation is wired inside the fence and the checks are green. Two defects remain: the direct no-engine path reports success whatever the inbox decided, and a lifecycle is carried across a restart only when a hold is already journaled, so a crash can silently drop an accepted pause.

## Findings
- correctness_review at squatch/__main__.py:200: In the no-engine path, `_control` ignores the tuple returned by `asyncio.run(inbox.consume(pause.apply))`. It prints `applied {verb}` and returns EXIT_OK even when the decision is `stale`. For example, `squatch resume --hold-id <wrong or already-released id>` with no engine running journals a stale decision and leaves the hold in place, yet tells the operator `applied resume` with exit 0. The message also prints `request.request_id` as the `hold id` for resume; that is the release request's own id, not a hold id. The live-lock path has the same mislabel. That is not fail-closed: the operator is told a pause was released when it was not. (paved road: Look up this request's decision in the consume result. When the outcome is not `accepted`, raise `Refusal` (non-zero exit) with the decision reason and a paved road such as 'check the active hold id'. Print `hold id` only for pause, where the request id really is the hold. For resume, print the hold being released (`args.hold_id`), or call the value a request id.)
- correctness_review at squatch/control.py:95: `active_lifecycle` looks only at unreleased `control_hold` events. `compose_daemon_control` mints a fresh lifecycle whenever no hold is journaled. Crash window: a pause request is journaled `accepted` (applied=false), then the process dies before `DispatchPause.apply` journals the hold. On restart there is no active hold, so a new lifecycle is minted. The retry branch of `_consume` then decides the incomplete accepted pause `stale` ('accepted lifecycle ended'), and an accepted operator pause is silently lost. This breaks the 'retrying only incomplete accepted work' contract and the restart-rehydration criterion. I have not traced whether a lifecycle meant to rotate per run is what section 20 intends; the loss of accepted work is certain either way. (paved road: Have lifecycle rehydration also count accepted-but-unapplied `control_decision` events, reusing the lifecycle of the latest incomplete accepted decision (or of an active hold) before minting a new one. Add a composition test that journals an accepted, unapplied pause decision, restarts `compose_daemon_control`, and asserts the pause is applied and the hold is created.)
