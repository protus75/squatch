## Outcome

ok

## Surprises / judgment calls

The planned `core` CLI has no host-routing or filesystem-write contract yet, so it is registered as a non-mutating availability verb. The renderer is a pure string transform and treats any marker-like corruption as a refusal.

## Dead ends

The first marker-position check compared the opening HTML marker offset instead of the embedded `squatch:core` offset; the focused idempotence test caught it and the parser was corrected.

## Second problems filed


## Resolved engine/model

OpenAI Codex (model identity not exposed to this run).

## Predicted vs actual

Expected: 75m. Actual: about 15m.
