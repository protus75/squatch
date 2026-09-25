## Outcome
ok

## Surprises / judgment calls
The re-entry branch retained the prior attempt's artifacts but not its code diff. I reconstructed the accepted implementation and followed the prior review's paved road: projection reads use a module-level `read_segments`, while `Journal.read_segments`, `Journal.read`, and `read_events` share one `_read_segments` parser owner without a partially initialized `Journal`.

## Dead ends
None.

## Second problems filed

## Resolved engine/model
OpenAI / GPT-5

## Predicted vs actual
Expected: 60m. Actual: approximately 15m.
