## Outcome

premise_failed

## Surprises / judgment calls

The fixed ownership contract excludes the production composition and live-Timers
lifetime seams that the provider behavior requires. I left the contract unchanged
because the governing plan is outside this ticket's scope fence.

## Dead ends

The required focused verification cannot run on the untouched base because
`tests/test_seeded_phase4_02.py` has not yet been authored. More importantly,
`squatch/stages.py` and `squatch/merge.py` compose the pipeline registry, while
`squatch/restart.py` and `squatch/daemon.py` own the live timers seam; none may be
added to the required provider fence without changing the plan-owned contract.

## Second problems filed


## Resolved engine/model

OpenAI Codex, model unknown.

## Predicted vs actual

Expected 75m; actual approximately 5m.
