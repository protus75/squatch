---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: high
agent_effort: high
---
## Depends on
- phase3-continue-13

## Context
- tests/test_seeded_phase3_11.py
- squatch/daemon.py
- squatch/__main__.py
- squatch/reconcile.py
- tests/test_reconcile.py
- squatch/heartbeat.py
- tests/test_heartbeat.py
- tests/test_control_cli.py
- tests/test_daemon_composition.py

## Plan contract
- section 20

## Goal
Reap interrupted work before dispatch and persist restart-safe timers.

## Why
Heartbeat establishes liveness; restart recovery and durable deadlines now need the same daemon lifecycle boundary.

## Scope in
Implement `squatch/restart.py`, `squatch/timers.py`, and `tests/test_restart_timers.py`, with `squatch/daemon.py` and `squatch/__main__.py` as the exact composition hooks. Restart reaping already exists in `squatch/reconcile.py` and is called before dispatch from the runner path: `restart.py` delegates to that reconciliation path and introduces no second reap path. Keep `squatch/reconcile.py` and `tests/test_reconcile.py` unchanged as preservation Context.

Timers are journaled deadlines: append through the Journal seam, read time through the injected Clock, and re-arm from a journal fold at `compose_daemon_*`. Re-arm once after restart; an expired deadline fires once; a fired deadline never re-arms. Do not add a side-file store. Keep the dormant heartbeat and its test unchanged; heartbeat remains dormant.

Use the existing control CLI and daemon composition tests as the predecessor-test closure. Reap happens before dispatch without `squatch/drain.py` or another inferred hook.

## Scope out
Do not add `squatch/drain.py`, another composition hook, a second reap implementation, a side-file timer store, or activate heartbeat.

## Scope fence
- squatch/restart.py
- squatch/timers.py
- tests/test_restart_timers.py
- squatch/daemon.py
- squatch/__main__.py

## Acceptance criteria
- `tests/test_restart_timers.py` proves restart composition delegates orphan reaping to the existing reconcile path before any dispatch offer, without a second reap path.
- `tests/test_restart_timers.py` proves journaled deadlines use the injected Clock, re-arm once from a journal fold after restart, fires an expired deadline once, and never re-arms a fired deadline.
- `tests/test_control_cli.py`, `tests/test_daemon_composition.py`, `tests/test_reconcile.py`, and `tests/test_heartbeat.py` remain green unchanged; heartbeat remains dormant.

## Verification
```
uv run pytest tests/test_restart_timers.py tests/test_reconcile.py tests/test_heartbeat.py tests/test_control_cli.py tests/test_daemon_composition.py -q
uv run pytest -q
```

## Definition of rejected
Stop if reap-before-dispatch needs `squatch/drain.py`, another unfenced path, an on-demand Context exception, a second reap path, or a non-journal timer store.

## Time budget
- expected: 75m
- stuck: 150m
