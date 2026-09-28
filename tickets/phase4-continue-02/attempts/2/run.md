## Outcome

ok

## Surprises / judgment calls

The rendered max-effort prompt correctly refuses content over its hard bound, so the
seed test temporarily lifts that bound only to measure and prove the on-demand
exception exceeds requisition headroom. The engine delimiter is checked through
`squatch.specs.DATA_MARKER`, allowing the established seeded-test Context to remain
valid.

## Dead ends

The initial ticket acceptance bullets did not all name their proving test, so ticket
lint refused them; they were narrowed to name the relevant test artifact.

## Second problems filed


## Resolved engine/model

OpenAI Codex (model identity not exposed to the implementer).

## Predicted vs actual

Expected: 75m. Actual: about 15m.
