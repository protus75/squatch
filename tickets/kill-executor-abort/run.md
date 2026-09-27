## Outcome

ok

## Surprises / judgment calls

`asyncio.wait` observes the cancelled Driver task's unwind without consuming either its result or cancellation, so the control consumer's own cancellation remains visible to its caller.

## Dead ends

None.

## Second problems filed

None.

## Resolved engine/model

OpenAI Codex; exact serving model unknown.

## Predicted vs actual

Expected: 75m. Actual: approximately 15m.
