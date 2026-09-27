## Outcome

premise_failed

## Surprises / judgment calls

The hold waits outside the merge slot and uses the lock holder's existing combined control consumer while blocked; release remains identity-bound through that one inbox.

## Dead ends

The full suite completed and exposed an unfenced direct `compose_pipeline` caller in `eval/shakeout/bench.py`. It must pass the now-mandatory shared inbox, but the scope fence forbids changing that path.

## Second problems filed

`eval/shakeout/bench.py` must be added to this ticket's scope fence (or updated by a follow-up) to inject the mandatory shared control inbox into its direct production pipeline construction.

## Resolved engine/model

OpenAI Codex / GPT-5

## Predicted vs actual

Expected 75m; stopped after about 40m on the scope-fence contradiction.
