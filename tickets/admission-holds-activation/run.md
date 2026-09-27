## Outcome

premise_failed

## Surprises / judgment calls

The shared control boundary is not injectable from the fenced production admission composition: `compose_pipeline` and `compose_merge_queue` have no `ControlInbox` input, and their caller creates neither one nor a control consumer for admission holds.

## Dead ends

Stopped before implementation. Passing the existing inbox requires changing `squatch/__main__.py` or `squatch/daemon.py`, both outside the scope fence. Creating an inbox in `squatch/merge.py` would create the forbidden second inbox and race the lock holder.

## Second problems filed


## Resolved engine/model

OpenAI Codex / GPT-5

## Predicted vs actual

Expected 75m; stopped during composition inspection because the required dependency is unavailable within the scope fence.
