## Outcome

ok

## Surprises / judgment calls

The re-entry branch did not contain the prior implementation, so I restored its fenced diff and then applied the carried review fix. A journaled acceptance is still returned for audit consistency after restart, but its governed mutation and hold release are skipped when the accepting lifecycle is no longer current.

## Dead ends


## Second problems filed


## Resolved engine/model

OpenAI GPT-5.

## Predicted vs actual

Expected 75m; actual approximately 10m.
