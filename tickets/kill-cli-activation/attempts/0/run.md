## Outcome
ok

## Surprises / judgment calls
The existing requisition test pins every pre-existing Context and on-demand file to its authoring-time byte size. I kept those files at the pinned sizes while adding the activation, so the max-effort render headroom proof remains valid. In-flight polling filters for typed kill requests so pause retains its existing next-boundary ordering.

## Dead ends
An initial shared in-flight control poll also consumed pause early, violating the preserved pause ordering test. The first implementation also exceeded the pinned authoring sizes; both were corrected before the final verification runs.

## Second problems filed

## Resolved engine/model
OpenAI Codex / GPT-5

## Predicted vs actual
Expected 75m; actual approximately 35m.
