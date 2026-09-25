## Outcome
premise_failed

## Surprises / judgment calls
- The prior attempt's finding reproduces on the landed base: `Bench.configure` accepts only `fake` and `sleep`, while `Bench.__init__` loads one config and constructs Runner and Drain from it.
- The ticket explicitly requires a routing fixture other than the instance's and explicitly rejects the ticket when the landed bench cannot run under one. Adding the needed bench seam would edit `eval/shakeout/bench.py`, outside the scope fence.

## Dead ends
- Private replacement of `bench.config`, `bench.runner._config`, and `bench._drain._config` was rejected in attempt 0 and is not a valid public routing-fixture seam; it can desynchronize the bench's state directory, redactor, journal, Runner, and Drain.
- Both `identical_terminals_climb` and `identical_terminals_reject_when_exhausted` are blocked. No fenced production or test file was edited, and no commit was created, as required for `premise_failed`.

## Second problems filed

## Resolved engine/model
OpenAI / Codex (exact serving model not exposed)

## Predicted vs actual
45m / about 5m to reproduce the blocker and run the untouched-base suite (`816 passed`)
