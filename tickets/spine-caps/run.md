## Outcome
ok

## Surprises / judgment calls
The shared fold is represented as `CapFold` so the drain can compute all named counts once per scan while `remaining` and `spent` also accept raw journal events for other callers.

## Dead ends
The first focused terminal test compared the git helper's newline-terminated CLI output without stripping it; the assertion was corrected and all verification commands then passed.

## Second problems filed

## Resolved engine/model
OpenAI / GPT-5

## Predicted vs actual
Expected 60m; actual approximately 12m.
