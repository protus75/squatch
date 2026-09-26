## Outcome

ok

## Surprises / judgment calls

The queue's public callback interface does not carry pre-rebase state, so the merge-local subtype retains that state around its public `admit` call and clears the adapter maps on unwind.

## Dead ends

None.

## Second problems filed

None.

## Resolved engine/model

OpenAI Codex

## Predicted vs actual

Expected 75m; actual approximately 35m.
