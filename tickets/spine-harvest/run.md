## Outcome
ok

## Surprises / judgment calls
Kept harvest commits on the existing stage-owned lift by extracting allowlisted bytes in `squatch.harvest` and exposing the lift as a shared stage-layer function. Setup-death fakes return a terminal object with a non-materialized workspace so the runner can journal `harvest: null` without inventing a second path.

## Dead ends
The first focused full-suite run exposed older drain and merge fakes still returning bare outcome strings; they were updated to the new Delivery seam. A direct `ruff` invocation was unavailable on PATH, so correctness was established with the ticket's complete pytest verification and `git diff --check`.

## Second problems filed

## Resolved engine/model
OpenAI / GPT-5

## Predicted vs actual
Expected 90m; actual approximately 45m.
