## Outcome
ok

## Surprises / judgment calls
Kept `reports` as a lifetime count. A callback-free tombstone stalled at K=3 retries the stable `/3` journal key, while an already reopened record that is tombstoned again does not reopen on its next report. Moved the retro bridge ahead of ticket commit and made semantic tombstone arrivals resolve before their shared rereport count.

## Dead ends
An initial K=3 retry branch could not distinguish a callback-free stalled tombstone from an already reopened record tombstoned again; the one-shot reopen marker supplies that distinction without adding state.

## Second problems filed

## Resolved engine/model
OpenAI Codex / GPT-5

## Predicted vs actual
Expected 75m; actual approximately 20m for this retry.
