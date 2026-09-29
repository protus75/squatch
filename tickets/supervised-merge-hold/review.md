---
verdict: snag
reviewed_sha: fd271211d0fabd0a2554194fcb7f115b3bca9801
produced_by_spec_version: '1.0'
produced_at_sha: fd271211d0fabd0a2554194fcb7f115b3bca9801
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The hold boundary, dispatch exclusion, identity-bound confirm and restart reconstruction are all wired, and the checks pass. Two defects remain. On the offline `squatch confirm` path the release regate replays a cached result from the old main instead of running again. Moving the terminal handling into a new function also changed failure routing to use the ticket's base rung instead of the escalated rung.

## Findings
- correctness_review at squatch/__main__.py:680: `_locked` passes `supervised=(verb == "serve")`. When `squatch confirm` takes the lock itself (no daemon running), the release pipeline is built with supervised=False. `compose_pipeline`'s regate then calls `merge._regate(...)` without `effect_identity`, so the key is `effect_key("regate", stem, run_seq)`. That is the same key the held admission already completed. `Effects.run` returns the stored completion for a known key (effects.py:56-57), so the release gets the invoice computed against the old main instead of regating against the moved main. The ticket's Definition of rejected lists this as stale-main integration. The tests miss it because their factory forces `supervised=True`, which is not the production CLI composition. (paved road: Always key the admission regate by the candidate's base (`effect_identity=state.slip.base`), or at minimum whenever `state.releasing` is set, whatever the verb. Add a test that builds the release through the same composition `_locked` uses for the `confirm` verb.)
- correctness_review at squatch/runner.py:462: `route(...)` used to get `current=Rung(tier, effort)`, where `tier, effort = effective(ticket, rungs(journal.read(), stem))` is the rung after escalation. The new `_finish_delivery` passes `Rung(ticket.agent_tier, ticket.agent_effort)`, the ticket's base rung. After an escalation, every failed dispatch is now routed as if it ran on the base rung, which breaks escalation and ladder decisions. This behavior change is unrelated to the ticket. (paved road: In `_finish_delivery`, compute `tier, effort = effective(ticket, rungs(journal.read(), ticket.stem))` (or pass the effective rung in from the caller) and route with `Rung(tier, effort)` as before.)
