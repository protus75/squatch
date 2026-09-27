## Outcome

premise_failed

## Surprises / judgment calls

The predecessor exposes pause constructor arguments on `Drain`, but the sole writable journal is created later inside `Runner.session()` and is not exposed through a fenced public composition seam. I treated private-method calls, a second journal writer, and an independently defaulted inbox as invalid workarounds because they violate the cited control-channel contract and repeat prior review findings.

## Dead ends

Real production composition requires an unfenced ownership change. `squatch/drain.py` or `squatch/runner.py` must expose the lock-held session journal when constructing the drain control boundary; required constructor injection of the shared admission hold through `compose_merge_queue` also requires `squatch/merge.py`. Those paths are outside the Scope fence, and the ticket explicitly requires `premise_failed` when real composition needs an unfenced path.

## Second problems filed

None.

## Resolved engine/model

OpenAI Codex (model identity unavailable).

## Predicted vs actual

Expected 75m; actual approximately 20m before the scope-fence blocker was proven.
