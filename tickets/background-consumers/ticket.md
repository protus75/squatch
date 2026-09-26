---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- phase3-continue-07

## Context
- squatch/daemon.py
- squatch/watcher.py
- squatch/scheduler.py
- squatch/triage.py
- squatch/box.py
- squatch/rework.py
- tests/test_daemon_composition.py

## Plan contract
- section 20

## Goal
Own the daemon's three background consumer task lifetimes.

## Why
The composed boundaries need one explicit in-process lifetime owner before durable control requests arrive.

## Scope in
Add `tests/test_daemon_tasks.py` and a daemon owner over three injected awaitable callbacks. Callback construction remains deferred. The watcher callback supplies one priority snapshot to `Watcher.observed`; the merge callback consumes one post-admission Rework handoff with callback-supplied SHA; the box callback performs one `Triage.run` pass. The owner starts all loops, owns their repetition and lifetime, awaits them at shutdown, and observes cancellation. If one callback raises, shutdown cancels and awaits siblings then re-raises that exception. Test each consumer lifetime independently, plus clean shutdown, cancellation, and sibling cleanup on exception. Preserve `tests/test_daemon_composition.py` unchanged and run it.

```yaml
ownership:
  background-consumers:
    owns:
      - tests/test_daemon_tasks.py
    hooks:
      - squatch/daemon.py
```

## Scope out
Do not add an observation source, SHA source, Triage composition, typed inbox, request policy, or CLI verb.

## Scope fence
- tests/test_daemon_tasks.py
- squatch/daemon.py

## Acceptance criteria
- `tests/test_daemon_tasks.py` proves the three callback boundaries with one independently named test for each consumer lifetime.
- `tests/test_daemon_tasks.py` proves cancellation, clean shutdown, and that a callback exception cancels and awaits siblings before the owner's shutdown await re-raises that exception.
- `tests/test_daemon_composition.py` remains unchanged and passes.

## Verification
```
uv run pytest tests/test_daemon_tasks.py tests/test_daemon_composition.py -q
uv run pytest -q
```

## Definition of rejected
Stop if a callback requires a new source or a predecessor assertion requires an unfenced edit.

## Time budget
- expected: 75m
- stuck: 150m
