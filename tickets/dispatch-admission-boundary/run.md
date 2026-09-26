## Outcome

ok

## Surprises / judgment calls

The admission handle is the task returned to its caller; a done observer clears the slot without consuming that task's result, exception, or cancellation.

## Dead ends

The synthetic dormancy fixture initially omitted a local `daemon.py`, so the closure scanner correctly did not consider the injected edge reachable. The fixture now supplies that local module.

## Second problems filed


## Resolved engine/model

OpenAI Codex / GPT-5

## Predicted vs actual

Expected 75m; actual about 10m.
