## Outcome

premise_failed

## Surprises / judgment calls

The production drain has pause injection but opens its lock-held Journal inside `Drain.run()`. I did not create a second inbox/journal writer or route through private drain methods.

## Dead ends

Real production pause/resume requires constructing the shared ControlInbox from the lock-held journal and passing it into `Drain`. That requires a change to `squatch/drain.py` or `squatch/runner.py`, neither of which is in the Scope fence. The first required verification command also cannot collect because the ticket requires `tests/test_control_cli.py`, but that file is absent on this base.

## Second problems filed

None.

## Resolved engine/model

OpenAI Codex (model identity unavailable).

## Predicted vs actual

Expected 75m; actual approximately 12m before the scope-fence blocker was proven.
