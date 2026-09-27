## Outcome
ok

## Surprises / judgment calls
The dispatch pause could not consume the inbox concurrently with the production control worker: a kill might otherwise be accepted through the pause-only callback and never reach worker-stop. I used a read-only pause view for dispatch, kept the control worker as the sole inbox consumer, and cached one production pipeline per serve journal so kill reaches the exact Stages executor that launched the active run.

## Dead ends
The first composition passed the existing consuming DispatchPause directly to daemon dispatch. The active-run kill proof exposed the competing-consumer hazard, so that shape was replaced before the final verification runs.

## Second problems filed
None.

## Resolved engine/model
OpenAI / GPT-5 (Codex).

## Predicted vs actual
Expected 75m; actual approximately 40m.
