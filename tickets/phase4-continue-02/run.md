## Outcome

ok

## Surprises / judgment calls

The authored ticket files were already present from the engine's prior lift, so this
attempt committed only the required test contract. The Phase 4 seed scans every
Context file for `DATA_MARKER`, including provider-owned paths, and renders the
authoring-time section-20 fixture.

## Dead ends

The first caller-closure scan matched this new seed test itself; it was excluded
because it is the contract checker, not a migrated provider caller.

## Second problems filed

None.

## Resolved engine/model

OpenAI Codex (exact serving model not exposed).

## Predicted vs actual

Expected 75m; actual approximately 35m in this attempt.
