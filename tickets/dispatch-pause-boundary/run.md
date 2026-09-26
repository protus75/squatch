## Outcome

ok

## Surprises / judgment calls

The prior reviewed implementation was not present in the retry worktree, so I restored its five fence-owned paths from its reviewed commit and changed only the ineffective dormancy proof. The replacement drives the real drain composition root with a constructor probe and also pins the control inbox to no initial holds.

## Dead ends

The earlier `not isinstance(control, DispatchPause)` assertion could never fail because `compose_daemon_control` returns a `ControlInbox`; it was replaced rather than retained.

## Second problems filed


## Resolved engine/model

OpenAI Codex; GPT-5.

## Predicted vs actual

Expected: 75m. Actual: about 15m for this retry.
