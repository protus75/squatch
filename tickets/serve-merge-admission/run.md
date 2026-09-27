## Outcome
ok

## Surprises / judgment calls
The queue adapter retains the delivered ticket metadata and squash commit until the serial slot unwinds so successful finalization occurs exactly once. An unresolved rung-2 result is mapped to the runner's closed `gate_failed` outcome with a typed `post_rebase_regate` finding while the queue preserves its Rework handoff.

## Dead ends
The prior attempt exposed the queue's internal `rework` outcome through `Delivery`, which the Runner rejects. This attempt replaced that boundary with the closed outcome mapping and exercised it through Serve's real watcher-to-Runner dispatch path.

## Second problems filed

## Resolved engine/model
OpenAI Codex / GPT-5

## Predicted vs actual
Expected 90m; actual approximately 20m for this retry.
