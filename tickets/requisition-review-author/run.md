## Outcome
ok

## Surprises / judgment calls
The untouched base suite was green at 750 tests. I reused `TicketSchemaGate.check` as the Author resolver's admission decision, so missing-plan, reserved-stem, collision, and grammar behavior cannot drift. The driver still makes one complete `run_gates` call before applying the terminal-findings predicate.

## Dead ends
The prior resolver copied the schema predicate and crashed when `SQUATCH_PLAN.md` was absent. I discarded that approach and passed the target admitted by the actual schema gate to `RequisitionGate` instead.

## Second problems filed

## Resolved engine/model
OpenAI / GPT-5 Codex

## Predicted vs actual
Expected 60m; actual about 25m, including the untouched-base proof and all three verification runs.
