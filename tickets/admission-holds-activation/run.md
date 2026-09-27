## Outcome

premise_failed

## Surprises / judgment calls

The hold waits outside the merge slot and invokes the lock holder's existing control consumer while blocked, so another admission is never serialized behind a waiting release.

## Dead ends

The full-suite invocation reached 63% before the execution environment terminated it at roughly 30 seconds; the prescribed scoped suite completed green.

## Second problems filed


## Resolved engine/model

OpenAI Codex / GPT-5

## Predicted vs actual

Expected 75m; stopped after about 35m when the full-suite command could not complete in this execution environment.
