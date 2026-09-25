## Outcome
ok

## Surprises / judgment calls
The attempt branch was recreated from current main, so I recovered the prior fenced implementation from its still-addressable commits before applying the carried review fixes. Box record failures now have a dedicated corruption type, leaving journal and projection failures outside the box refusal. The instance box already contained all 257 bootstrap messages, so I did not re-ingest them.

## Dead ends

## Second problems filed

## Resolved engine/model
OpenAI Codex / GPT-5 / implement spec 1.1

## Predicted vs actual
Expected 90m; actual approximately 20m, including base verification, recovery of the prior implementation, both review fixes, and all verification passes.
