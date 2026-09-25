## Outcome
ok

## Surprises / judgment calls
None.

## Dead ends
The prior implementation special-cased exhausted-ladder arrivals in Reject resolution. That path was removed because the ticket requires the existing funded auto-keep behavior to remain unchanged; the exhaustion test now proves the ladder terminal occurred and that retries continue until the retry cap leaves the stem reported in the Reject queue.

## Second problems filed
None.

## Resolved engine/model
OpenAI / Codex (GPT-5).

## Predicted vs actual
Expected 90m; this correction took approximately 15m. The untouched base passed 679 tests and the committed implementation passes all 694 tests.
