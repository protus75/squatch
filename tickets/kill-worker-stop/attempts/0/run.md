## Outcome

ok

## Surprises / judgment calls

Repeated worker stopping keeps the control task separate from the worker set, so a later accepted kill is a no-op for workers rather than a self-cancellation.

## Dead ends

The first repeated-stop implementation derived workers from the current task tuple, which would have selected the control task after the first stop; worker ownership is now retained separately.

## Second problems filed


## Resolved engine/model

OpenAI / GPT-5 Codex.

## Predicted vs actual

Expected 75m; actual about 25m.
