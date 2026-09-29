## Outcome
ok

## Surprises / judgment calls
The engine had already lifted all three row-one seed tickets. I preserved
those contracts and added the missing continuation custody clauses to the
lifted row-two ticket without committing anything under `tickets/`.

## Dead ends
An earlier reviewed implementation pinned only continuation dependency edges;
it did not pin the exact fence and sole Context for continuations 03 through
08. The replacement assertion extracts every explicit custody clause.

## Second problems filed

## Resolved engine/model
OpenAI / Codex.

## Predicted vs actual
Expected 75 minutes; actual approximately 20 minutes. Focused verification:
6 passed. Full verification: 1554 passed.
