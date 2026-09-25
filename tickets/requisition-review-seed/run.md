## Outcome
ok

## Surprises / judgment calls
The prior implementation was available only as dangling commits after the failed attempt, so I restored it and kept its reviewed design. Seed replay now skips the shared intake lane only for byte-identical prior output, retaining the original authoring commit from the prior intake signal; interrupted effects recognize their already-committed members from the effect window.

## Dead ends
The prior clean-path fallback in the shared intake lane was rejected because it emitted false authoring signals for ordinary callers. It was reverted and replaced with seed-effect-local replay handling.

## Second problems filed
None.

## Resolved engine/model
OpenAI / GPT-5

## Predicted vs actual
Expected 90m; actual approximately 18m on this re-entry.
