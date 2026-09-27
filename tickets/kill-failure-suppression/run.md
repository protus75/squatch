## Outcome

ok

## Surprises / judgment calls

Separated kill-specific suppression from the existing generic worker-stop state so an accepted kill is the sole path that holds the control consumer open after worker cancellation.

## Dead ends

The initial stale-request test allowed an independent failure before the control pass consumed the request; it was revised to observe the stale decision before releasing that failure.

## Second problems filed


## Resolved engine/model

OpenAI / GPT-5

## Predicted vs actual

Expected 75m; actual about 10m.
