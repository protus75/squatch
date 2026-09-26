## Outcome
premise_failed

## Surprises / judgment calls
Making `Pipeline.merge_queue` required, as required by the ticket and prior finding, changes the `Pipeline` constructor contract.

## Dead ends
`rg` found direct `Pipeline(stages, merge)` call sites in `tests/test_merge.py`, `tests/test_drain_reentry.py`, and `tests/test_terminal.py`. They are outside the scope fence, and the ticket says to stop if such a call site needs editing.

## Second problems filed

## Resolved engine/model
OpenAI Codex / GPT-5

## Predicted vs actual
Expected: 75m. Actual: stopped during contract and call-site audit.
