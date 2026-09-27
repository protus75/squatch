---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- kill-worker-stop

## Context
- squatch/daemon.py
- tests/test_kill_executor_abort.py
- tests/test_kill_signal_journal.py
- tests/test_daemon_tasks.py

## Plan contract
- section 20

## Goal
Construct the post-kill failure-path suppression boundary.

## Why
An intentional kill must not turn its own cancellation outcomes into failure recovery work.

## Scope in
Add `tests/test_kill_failure_suppression.py` and extend only the dormant kill composition in `squatch/daemon.py` with post-kill failure-path suppression. Establish intentional-stop state only after an accepted current-lifecycle kill decision and before its cancellation can be observed as failure. Cancellation caused by that stop must not trigger ordinary failure reporting, recovery, or a replacement worker. Preserve executor unwind and worker stop ordering; preserve unrelated exceptions and ordinary no-kill task failure propagation. A stale kill must not enable suppression. Do not broadly swallow exceptions or an external cancellation of the control consumer.

Direct tests exercise the real daemon boundary with deterministic blocked workers, including kill-caused cancellation, a stale request, an independent worker error, and cancellation of the control consumer. Keep `driver_abort_consumer(inbox, driver)` and the ordinary DaemonTasks contract unchanged. The worker-stop sibling's new test is omitted from Context because it does not exist at authoring; inspect it after its dependency merges and run it unchanged as preservation evidence. The existing executor, signal, and task tests are preservation-only suites.

```yaml
ownership:
  kill-failure-suppression:
    owns:
    - tests/test_kill_failure_suppression.py
    hooks:
    - squatch/daemon.py
```

## Scope out
Do not add the kill CLI verb, activate production routing, change the Driver or reporting modules, or edit predecessor tests.

## Scope fence
- tests/test_kill_failure_suppression.py
- squatch/daemon.py

## Acceptance criteria
- `tests/test_kill_failure_suppression.py` proves intentional kill cancellations produce no ordinary failure recovery/reporting or replacement workers, while all stopped tasks are observed.
- `tests/test_kill_failure_suppression.py` proves stale kills and independent failures are not suppressed, and external control cancellation still propagates.
- `tests/test_kill_worker_stop.py`, `tests/test_kill_executor_abort.py`, `tests/test_daemon_tasks.py`, and `tests/test_kill_signal_journal.py` remain green unchanged, preserving stop ordering, executor abort, ordinary failures, and CLI dormancy.

## Verification
```
uv run pytest tests/test_kill_failure_suppression.py tests/test_kill_worker_stop.py tests/test_kill_executor_abort.py tests/test_kill_signal_journal.py tests/test_daemon_tasks.py -q
uv run pytest -q
```

## Definition of rejected
Stop if suppression requires changing an unfenced failure producer or predecessor test.

## Time budget
- expected: 75m
- stuck: 150m
