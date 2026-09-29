## Outcome

implemented

## Surprises / judgment calls

Normal host worktrees do not contain `squatch/hostfiles.py`, so the gate uses the shipped template there and reads a literal candidate template only for self-hosted branch worktrees.

## Dead ends

The first merge-suite run treated every host as self-hosted and failed when its fixture worktrees had no `squatch/hostfiles.py`; the fallback above resolved it.

## Second problems filed


## Resolved engine/model

OpenAI Codex (GPT-5)

## Predicted vs actual

Expected 75m; actual about 20m.
