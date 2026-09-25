## Outcome
premise_failed

## Surprises / judgment calls
The untouched base suite is green (809 tests), and the injected stuck-budget seam is present. The required cumulative shakeout command nevertheless cannot re-confirm the prior stages group.

## Dead ends
On the untouched base, `uv run python -m eval.shakeout run --outbox tickets/shakeout-driver --prior tickets/shakeout-stages/shakeout-report.json` exits 2. `shakeout-stages.timeout_dead_ends` raises `StopIteration`: with its zero-minute budget, the clock-derived deadline expires before the first fake task consumes its scripted `Hang`, so the second run consumes the hang again and no re-entry Implement prompt contains the marker. Repair requires changing `eval/shakeout/stages_group.py`, outside this ticket's scope fence; the Definition of rejected requires stopping when a prior entry cannot be re-confirmed byte-for-byte.

## Second problems filed
The prior `shakeout-stages.timeout_dead_ends` fixture relies on the pre-sleep-seam scheduling behavior of a zero-second stuck budget and must be updated by its owning group.

## Resolved engine/model
OpenAI / GPT-5 (Codex)

## Predicted vs actual
60m / about 20m
