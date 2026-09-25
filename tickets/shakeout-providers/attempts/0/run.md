## Outcome
premise_failed

## Surprises / judgment calls
The provider exception can carry `auth_error` and its login road into the Driver's `infra_error` StageResult without changing the driver. However, `Runner.dispatch` replaces a non-ok delivery reason with finding codes or the stable outcome token before journaling the terminal, and `Drain._tail` does not render the delivery or diagnosis reason in its `parked:` line.

## Dead ends
The required observable cannot be produced inside the scope fence. Making the journal terminal reason carry `auth_error` and the re-authentication road requires changing `squatch/runner.py`; making the drain's parked line name that road requires changing `squatch/drain.py`. Both paths are outside the fence, and the ticket explicitly requires `premise_failed` when an outside-fence file must change.

## Second problems filed

## Resolved engine/model
OpenAI Codex / GPT-5

## Predicted vs actual
Expected 60m; actual under 15m before the scope-fence blocker was proven.
