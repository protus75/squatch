---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- kill-signal-journal

## Context
- squatch/daemon.py
- squatch/driver.py

## Plan contract
- section 20

## Goal
Construct cancellation of the active Driver invocation.

## Why
The journaled kill decision needs one independently provable executor-unwind boundary before workers or failures acquire policy.

## Scope in
Add `tests/test_kill_executor_abort.py` and hook the dormant daemon kill boundary to the active `Driver` invocation. A journaled current-lifecycle kill reaches that invocation, cancels it, and awaits its unwind while preserving `asyncio.CancelledError` propagation to the active caller. Prove cancellation reaches the real active Driver call and is not swallowed. Do not add worker-stop behavior, failure suppression, or a kill CLI verb.

```yaml
ownership:
  kill-executor-abort:
    owns:
    - tests/test_kill_executor_abort.py
    hooks:
    - squatch/daemon.py
    - squatch/driver.py
```

## Scope out
Do not add a kill CLI verb, worker-stop policy, or failure suppression.

## Scope fence
- tests/test_kill_executor_abort.py
- squatch/daemon.py
- squatch/driver.py

## Acceptance criteria
- `tests/test_kill_executor_abort.py` proves a journaled accepted kill reaches and unwinds the active Driver invocation.
- `tests/test_kill_executor_abort.py` proves cancellation propagation is preserved and no worker-stop or failure-suppression behavior is introduced.

## Verification
```
uv run pytest tests/test_kill_executor_abort.py tests/test_kill_signal_journal.py -q
uv run pytest -q
```

## Definition of rejected
Stop if active Driver cancellation cannot be proved without an unfenced path.

## Time budget
- expected: 75m
- stuck: 150m
