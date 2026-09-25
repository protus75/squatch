---
verdict: snag
reviewed_sha: e68a0469102961369dbc9d12dd53dc6f9edd5a1d
produced_by_spec_version: '1.0'
produced_at_sha: e68a0469102961369dbc9d12dd53dc6f9edd5a1d
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The box-path wiring is sound and tested, and every acceptance criterion has a covering test. Two problems remain: the review resolver's grammar pre-check misses one grammar rule, so the review can run on a ticket that fails the grammar gate, and the driver.py change goes beyond the condition the Scope in section sets for touching the driver.

## Findings
- correctness_review at squatch/author.py:104: The ticket requires that the review runs only when the grammar gate passes. `_ReviewCapture.targets` copies only part of `TicketSchemaGate.check`: it skips on-disk collisions and `lint_ticket` failures, but not a stem in `RESERVED_STEMS` (for example `decisions` or `retro`). `run_gates` runs every gate, so an authored ticket with a reserved stem and an otherwise valid body fails `ticket_schema` and still gets a `requisition_review` call. That call is wasted. If the review answers `rma`, `terminal_findings` ends the pass as an rma, even though the grammar finding was fixable by re-authoring. Because the findings are mixed, the verdict is also not recorded on the message's `triage` field, while the report still says rma. (paved road: Have `targets` return `()` whenever `TicketSchemaGate` would fail, including when `artifact.stem in RESERVED_STEMS`. The cleanest way is to reuse one shared predicate or the gate's own check rather than a partial copy. Add a test where a reserved stem gets no review call.)
- correctness_review at squatch/driver.py:134: The Scope in section allows a driver.py change only if the gate loop cannot run an async gate that makes its own driver call. The diff's own `test_async_gate_can_make_its_own_driver_call` shows the loop already can, and that test does not use the new code. The added `terminal_findings` parameter is a new driver capability for a different purpose: stopping on rma. That is outside the condition the ticket set for changing this file. I am not certain this is a defect: the ticket also requires rma to end the pass with no further call, and a crashing gate is turned into a finding, so the Author may have no clean way to stop without a driver change. If so, the ticket is internally inconsistent and needs amending; the driver change should not quietly widen the fence. (paved road: Either make rma end the pass without changing driver.py, or, if that is truly impossible, file the conflict so the ticket or plan explicitly allows the driver's early-stop hook, then land it against that amended contract.)
