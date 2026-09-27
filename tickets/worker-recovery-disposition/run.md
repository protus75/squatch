## Outcome
ok

## Surprises / judgment calls
Used the orphan terminal as the restart idempotency boundary, as specified, rather than adding a second deduplication mechanism. The absent-worktree restart proof settles each redispatched test run so a later reconciliation can distinguish a duplicate recovery from a genuinely new orphan.

## Dead ends
The first absent-worktree ordering probe accumulated later prune snapshots; it was narrowed to the snapshot taken at reconciliation. The initial restart proof used an `ok` fake delivery, which intentionally leaves a running transition in this harness, so it was changed to a terminal `gate_failed` delivery.

## Second problems filed

## Resolved engine/model
OpenAI Codex / GPT-5

## Predicted vs actual
Expected: 75m. Actual: about 15m.
