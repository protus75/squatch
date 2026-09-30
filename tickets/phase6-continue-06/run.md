## Outcome
premise_failed

## Surprises / judgment calls
The required embedded Context for `go-grade-machinery` makes a truthful
section-20-only maximum-effort render exceed the configured headroom. I did
not replace that proof with a synthetic or reduced Context render.

## Dead ends
`uv run pytest tests/test_seeded_phase6_06.py -q` reports a 129126-character
render for `go-grade-machinery` against the 120000-character bound. Reducing
the ticket prose cannot close the required margin while retaining the required
Context. The governing plan is outside this ticket's scope fence.

## Second problems filed

## Resolved engine/model
OpenAI Codex (model identity not exposed).

## Predicted vs actual
Expected: 75m. Actual: under 75m; blocked by the render-bound premise.
