## Outcome
ok

## Surprises / judgment calls
The untouched base suite was green at 750 tests. I preserved the driver's one `run_gates` call so every gate still runs, made Author's review target resolver skip the paid review when ticket grammar fails, and added only a caller-supplied terminal-finding predicate so an RMA can stop the Author loop immediately. The resolver also clears its captured verdict on every attempt so a later grammar failure cannot record a stale review.

## Dead ends
An initial driver regression test reused an effect identity in the same journal and replayed the earlier call; changing the test ticket identity made the intended fresh call explicit.

## Second problems filed

## Resolved engine/model
OpenAI / GPT-5 Codex

## Predicted vs actual
Expected 60m; actual about 20m.
