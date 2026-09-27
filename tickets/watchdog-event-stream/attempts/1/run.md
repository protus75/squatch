## Outcome

ok

## Surprises / judgment calls

Replaced the prior attempt's `StreamReader.readline()` loop with chunked line splitting so JSONL records over 64 KiB preserve capture semantics. Callback failures also share the group kill-and-wait cleanup path.

## Dead ends

None.

## Second problems filed

None.

## Resolved engine/model

OpenAI Codex (model identity not exposed to this worktree).

## Predicted vs actual

Expected: 75m. Actual: about 20m.
