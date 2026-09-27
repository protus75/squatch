---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- phase3-continue-09

## Context
- squatch/control.py
- squatch/daemon.py

## Plan contract
- section 20

## Goal
Construct the identity-bound kill signal boundary.

## Why
The lock holder must record its decision before cancellation can change the active engine state.

## Scope in
Add `tests/test_kill_signal_journal.py` and construct a dormant kill request path through the lock-held control inbox and daemon composition. A kill request accepts only the current lifecycle identity, and the lock holder journals its accepted or stale decision before any cancellation mutation it governs. Directly prove the journal ordering and identity binding. Keep the boundary dormant: do not add a kill CLI verb, worker stopping, or failure suppression.

```yaml
ownership:
  kill-signal-journal:
    owns:
    - tests/test_kill_signal_journal.py
    hooks:
    - squatch/control.py
    - squatch/daemon.py
```

## Scope out
Do not activate a CLI verb, cancel a Driver invocation, stop workers, or suppress failures.

## Scope fence
- tests/test_kill_signal_journal.py
- squatch/control.py
- squatch/daemon.py

## Acceptance criteria
- `tests/test_kill_signal_journal.py` directly proves a current-lifecycle kill decision is journaled by the lock holder before its governed cancellation mutation, and stale identities fail closed.
- `tests/test_kill_signal_journal.py` proves the construction remains dormant and exposes no kill CLI verb.

## Verification
```
uv run pytest tests/test_kill_signal_journal.py tests/test_control.py -q
uv run pytest -q
```

## Definition of rejected
Stop if decision-before-mutation or lifecycle binding requires an unfenced path.

## Time budget
- expected: 75m
- stuck: 150m
