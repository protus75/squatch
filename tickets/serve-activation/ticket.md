---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: high
agent_effort: high
---
## Depends on
- phase3-continue-20
- daemon-soak

## Context
- squatch/daemon.py
- squatch/__main__.py
- tests/test_daemon_composition.py
- tests/test_daemon_tasks.py
- tests/test_heartbeat.py
- tests/test_storm.py

## Plan contract
- section 20

## Goal
Activate the production serve composition.

## Why
The daemon boundaries are dormant until one production owner composes their real continuous loop.

## Scope in
Add the `serve` verb and the production continuous loop in new `squatch/serve.py`. Compose the existing dispatch, watcher, merge, box, control, heartbeat, restart/timer, storm, checkpoint, and worker-task boundaries; reconcile before dispatch; hold the writer lock for the serve lifetime; and exit only through kill/signal or terminal worker failure. Activate worker-stop and kill-failure-suppression with decision-before-mutation and executor-unwind-before-worker-cancel order. Add `tests/test_serve.py`, construct the real production graph in-process without launching host work, replace the `serve`-absence assertions in `tests/test_daemon_composition.py` and `tests/test_heartbeat.py`, and migrate `tests/test_storm.py`'s production-root closure plus only invalidated predecessor dormancy assertions. The exact embedded Context is the six paths above. `tests/test_kill_worker_stop.py` and `tests/test_kill_failure_suppression.py` are fenced on-demand inspection exceptions; `squatch/runner.py` and other component modules remain read-only on-demand inspection only.

## Scope out
Do not run daemon soak, widen production-module authority, or change predecessor assertions that this activation does not invalidate.

## Scope fence
- squatch/serve.py
- squatch/daemon.py
- squatch/__main__.py
- tests/test_serve.py
- tests/test_daemon_composition.py
- tests/test_daemon_tasks.py
- tests/test_kill_worker_stop.py
- tests/test_kill_failure_suppression.py
- tests/test_heartbeat.py
- tests/test_storm.py

## Acceptance criteria
- `tests/test_serve.py` constructs the real production object graph in-process, proves `serve` composes every named boundary, reconciles before dispatch, retains one writer lock for its lifetime, and does not launch host work.
- `tests/test_daemon_tasks.py`, `tests/test_kill_worker_stop.py`, and `tests/test_kill_failure_suppression.py` prove worker-stop and failure suppression activate with decision-before-mutation and executor-unwind-before-worker-cancel order.
- `tests/test_daemon_composition.py`, `tests/test_heartbeat.py`, and `tests/test_storm.py` migrate only their invalidated serve-dormancy or production-root assertions and preserve their remaining contracts.

## Verification
```
uv run pytest tests/test_serve.py tests/test_daemon_composition.py tests/test_daemon_tasks.py tests/test_kill_worker_stop.py tests/test_kill_failure_suppression.py tests/test_heartbeat.py tests/test_storm.py -q
uv run pytest -q
```

## Definition of rejected
Reject a missing production serve boundary, a duplicate writer, dispatch before reconciliation, inactive worker-stop or failure suppression, or an edited read-only component module.

## Time budget
- expected: 75m
- stuck: 150m
