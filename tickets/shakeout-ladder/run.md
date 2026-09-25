## Outcome
ok

## Surprises / judgment calls
- Three direct public runs keep the identical-terminal detector isolated from the same-wall detector; the fourth dispatch is then driven by one drain so its retry draw proves the pending rung.
- After the exhausted-ladder terminal, the retry cap is lowered through `Bench.configure(config=...)` so the drain reports the existing Reject arrival instead of auto-keeping it. The terminal's routing reason remains the third run's exhausted-ladder decision.

## Dead ends
- The first generated fixture ticket described its observable without naming the fixture path in backticks, so intake refused it. The criterion now names `feature/<stem>.txt` and the cumulative run passes.

## Second problems filed

## Resolved engine/model
OpenAI / Codex (exact serving model not exposed)

## Predicted vs actual
45m / about 20m
