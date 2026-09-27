## Outcome

ok

## Surprises / judgment calls

The plan requires no change. The CLI's _RestartRunner wraps super().session() through compose_daemon_restart and restart_session. Entering that existing session delegates to Runner's one lock-held reconcile call; restart.py adds no reap call. Both real main entry paths (run and drain) are tested with the actual reconciler, proving exactly one reconciliation before the first Runner.dispatch offer. Runner, drain, reconcile, heartbeat, and all preservation tests remain unchanged.

Timers fold only timer_armed/timer_fired records marked kind=deadline, leaving the bootstrap drain's existing ceiling records under their current owner. Deadline identities are immutable: repeated arms are inert, changed timestamps are refused, and fired identities remain fired. Expired deadlines fire synchronously during composition; future deadlines use injected Clock and Sleep seams. The journal is the only durable store.

The restart wrapper awaits timer shutdown inside the delegated session, before journal closure and lock release, including exceptional exit. A regression test confirms Journal.append after closure raises ValueError: write to closed file, and proves pending timer cancellation finishes while the journal remains open. Timer write failures are observed at shutdown.

Committed implementation: e1db78ffc495e3327f71ffd1f643999ff55b90cc. Verification: the exact focused command passed 39 tests; uv run pytest -q passed 1082 tests. Only the five fenced paths are committed; this run record is uncommitted.

## Dead ends

No implementation was abandoned in this attempt. The prior-attempt dead dispatch hook and second direct reconcile entry point were not retained; the production restart wrapper delegates the complete existing session instead. Timer ownership is attached to that session rather than the pipeline factory.

## Second problems filed


## Resolved engine/model

OpenAI / GPT-6 (Codex).

## Predicted vs actual

Expected 75m; actual approximately 10m for this attempt, including both verification commands and committed-tree verification.
