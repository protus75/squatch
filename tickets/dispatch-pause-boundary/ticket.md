---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- phase3-continue-08

## Context
- tests/test_seeded_phase3_core.py
- squatch/daemon.py
- squatch/control.py
- squatch/drain.py
- tests/test_drain.py

## Plan contract
- section 20

## Goal
Construct the dispatch pause boundary and its bound release.

## Why
A pause must stop the next offer before it spends durable dispatch accounting.

## Scope in
Build a directly tested, dormant pause boundary in daemon/control with a matching hold-instance-bound release. Consume the control decision before every durable dispatch action, including `Drain._draw_retry`: the bootstrap drain hook must check before a re-offer spends a retry-cap draw, as well as before normal dispatch accounting. An already admitted operation completes non-preemptively. Only a matching resume releases the hold, latest-wins; stale lifecycle requests and pre-hold releases cannot affect later identities. Journal the decision before mutating governed state, using the existing ControlInbox and lock-held journal.

Own `tests/test_daemon_pause.py` and hook `tests/test_drain.py` to prove ordering with injected control requests, for both fresh offers and retries. Keep production control activation dormant until pause-resume-activation, and pin that dormancy in the new test for its successor to migrate. Use the existing admission slot without changing scheduler/watcher. Preserve `tests/test_daemon_tasks.py` and `tests/test_control.py` unchanged as preservation-only suites, outside this fence and Context.

```yaml
ownership:
  dispatch-pause-boundary:
    owns:
    - tests/test_daemon_pause.py
    hooks:
    - squatch/daemon.py
    - squatch/control.py
    - squatch/drain.py
    - tests/test_drain.py
```

## Scope out
Do not add CLI verbs, activate merge admission holds, implement kill, or edit the preservation-only suites.

## Scope fence
- tests/test_daemon_pause.py
- squatch/daemon.py
- squatch/control.py
- squatch/drain.py
- tests/test_drain.py

## Acceptance criteria
- `tests/test_daemon_pause.py` proves pause refuses new dispatch before accounting, preserves in-flight completion, and accepts only the current lifecycle and hold-bound release.
- `tests/test_drain.py` proves pause is observed before a retry draw and fresh dispatch accounting; release allows exactly the pending offer without spending while paused.
- `tests/test_daemon_pause.py` proves decision-before-mutation, latest-wins pause/resume ordering, and construction dormancy have direct tests; unchanged preservation-only suites pass.

## Verification
```
uv run pytest tests/test_daemon_pause.py tests/test_drain.py tests/test_daemon_tasks.py tests/test_control.py -q
uv run pytest -q
```

## Definition of rejected
Stop if pause before retry accounting or predecessor-test closure requires any path outside the fence.

## Time budget
- expected: 75m
- stuck: 150m
