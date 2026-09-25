## Outcome
ok

## Surprises / judgment calls
The prior implementation diff was not present on the retry branch, so it was restored from the prior attempt commit. The rejected drain test was strengthened to prove the machine confirm precedes dispatch and the green rerun merges.

## Dead ends
The first mechanical conversion of the prior commit's unified diff used unsupported numeric hunk headers; it changed no files and was retried with apply-patch section headers.

## Second problems filed

## Resolved engine/model
OpenAI Codex / GPT-5

## Predicted vs actual
Expected 75m; actual about 10m for the retry.
