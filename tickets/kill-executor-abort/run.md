## Outcome

ok

## Surprises / judgment calls

The prior implementation was restored from its retained commit, except for the reviewer-identified unreachable `current_task() is None` path. `asyncio.wait` observes the cancelled Driver task's unwind without consuming either its result or cancellation, so the control consumer's own cancellation remains visible to its caller.

## Dead ends

None.

## Second problems filed

None.

## Resolved engine/model

OpenAI Codex, GPT-5.

## Predicted vs actual

Expected: 75m. Actual: approximately 10m on this re-entry.
