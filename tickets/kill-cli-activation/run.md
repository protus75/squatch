## Outcome
ok

## Surprises / judgment calls
The prior green implementation was recoverable from its reviewed commit. I restored its scoped composition and added the carried review fix: a latched kill now ends the offer wait even while a pause hold remains, with a regression proving stop, lock release, and no admission or retry draw.

## Dead ends

## Second problems filed

## Resolved engine/model
OpenAI Codex / GPT-5

## Predicted vs actual
Expected 75m; actual approximately 20m.
