---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- phase3-continue-10

## Context
- squatch/daemon.py
- tests/test_kill_executor_abort.py
- tests/test_kill_signal_journal.py
- tests/test_daemon_tasks.py

## Plan contract
- section 20

## Goal
Construct the ordered kill boundary for owned background workers.

## Why
Executor unwind must precede stopping the daemon workers, without cancelling the control consumer performing the kill.

## Scope in
Add `tests/test_kill_worker_stop.py` and a separate dormant composition in `squatch/daemon.py` that consumes an accepted identity-bound kill, awaits the active Driver abort/unwind, then cancels and awaits DaemonTasks' sibling watcher, merge, and box tasks. Exclude the control task executing the kill from the stopped set: it must finish the mutation and let ControlInbox journal the applied decision without self-cancellation or self-await. Repeated application must not restart workers or leave pending tasks.

Keep `driver_abort_consumer(inbox, driver)`'s two-argument signature and behavior unchanged, including cancellation propagation. Preserve the ordinary DaemonTasks shutdown/run behavior. `tests/test_kill_executor_abort.py`, `tests/test_kill_signal_journal.py`, and `tests/test_daemon_tasks.py` are read-only Context and preservation-only verification suites. Use deterministic blocked callbacks to prove no worker is cancelled before executor unwind finishes and all three are awaited before the kill mutation completes. Stale identities do not stop workers. Construction remains dormant with no kill CLI verb; failure suppression is the next boundary.

```yaml
ownership:
  kill-worker-stop:
    owns:
    - tests/test_kill_worker_stop.py
    hooks:
    - squatch/daemon.py
```

## Scope out
Do not activate CLI/admission kill routing, change predecessor tests, or add post-kill failure suppression.

## Scope fence
- tests/test_kill_worker_stop.py
- squatch/daemon.py

## Acceptance criteria
- `tests/test_kill_worker_stop.py` proves accepted decision -> executor unwind -> watcher/merge/box cancellation and observation -> applied decision ordering, with no control-task cancellation or deadlock.
- `tests/test_kill_worker_stop.py` proves stale kills leave workers running and repeated kill application leaves no pending worker tasks.
- `tests/test_kill_executor_abort.py`, `tests/test_daemon_tasks.py`, and `tests/test_kill_signal_journal.py` remain green unchanged, preserving executor abort, ordinary task behavior, and CLI dormancy.

## Verification
```
uv run pytest tests/test_kill_worker_stop.py tests/test_kill_executor_abort.py tests/test_kill_signal_journal.py tests/test_daemon_tasks.py -q
uv run pytest -q
```

## Definition of rejected
Stop if worker ownership or predecessor preservation requires an unfenced path.

## Time budget
- expected: 75m
- stuck: 150m
