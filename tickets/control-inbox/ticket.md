---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- background-consumers

## Context
- squatch/daemon.py
- tests/test_daemon_composition.py

## Plan contract
- section 20

## Goal
Build the typed durable control inbox.

## Why
The lock-holding daemon needs crash-safe control intake without a second journal writer.

## Scope in
Add `squatch/control.py` and `tests/test_control.py`, and hook daemon consumption under its lock-held journal. Requests are typed, file-backed and crash-safe; lifecycle identity is restart-unique, release binds a hold instance, consumption is exactly once, and the decision is journaled before governed mutation. Stale lifecycle requests and releases predating a hold never affect later identities. Prove replay at crash points. `tests/test_daemon_tasks.py` is a hook, is run in Verification, and is deliberately not Context. Preserve `tests/test_daemon_composition.py` unchanged and run it.

```yaml
ownership:
  control-inbox:
    owns:
      - squatch/control.py
      - tests/test_control.py
    hooks:
      - squatch/daemon.py
      - tests/test_daemon_tasks.py
```

## Scope out
Do not activate pause or kill CLI verbs or alter task-consumer policy.

## Scope fence
- squatch/control.py
- tests/test_control.py
- squatch/daemon.py
- tests/test_daemon_tasks.py

## Acceptance criteria
- `tests/test_control.py` proves crash-safe publication, restart identity, exactly-once consumption, and decision-before-mutation.
- `tests/test_control.py` proves stale lifecycle and pre-hold releases cannot affect later identities.
- `tests/test_daemon_tasks.py` and unchanged `tests/test_daemon_composition.py` pass.

## Verification
```
uv run pytest tests/test_control.py tests/test_daemon_tasks.py tests/test_daemon_composition.py -q
uv run pytest -q
```

## Definition of rejected
Stop if exactly-once consumption or identity binding requires an unfenced path.

## Time budget
- expected: 75m
- stuck: 150m
