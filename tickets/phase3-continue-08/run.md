## Outcome

premise_failed

## Surprises / judgment calls

The prior finding reproduces on the current base: `Drain._drain` calls `_draw_retry` before `Runner.dispatch`, so its retry-cap journal write is durable dispatch accounting that a pause must prevent.

## Dead ends

The requested successor fences omit `squatch/drain.py` and its tests. Neither `squatch/daemon.py` nor the listed activation hooks can interpose before the drain's retry draw, so authoring the seeds would falsely claim a closure that the plan requires. The ticket's Definition of rejected requires stopping for this unfenced predecessor path.

## Second problems filed


## Resolved engine/model

OpenAI Codex (model identity not exposed).

## Predicted vs actual

Expected 75m; actual approximately 5m to reproduce the authoring defect.
