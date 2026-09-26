---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- phase3-continue-04

## Context

## Plan contract
- section 20

## Goal
Build the dormant single-flight admission/task boundary for daemon dispatch.

## Why
The daemon needs one owner of the interval between accepting an offer and observing its task's completion before scheduler activation can compose it.

## Scope in
Create `squatch/daemon.py` with a directly callable admission boundary and `tests/test_daemon_admission.py` with deterministic async proofs. Admission accepts a stem and an injected async work callback, reserves the single active slot before yielding, and owns the resulting task until completion is observed. A busy offer is refused without invoking its callback or creating another task; pending ordering remains the scheduler's job. Completion, failure, and cancellation release the slot without losing the task outcome. This is construction evidence, below production composition grade.

```yaml
ownership:
  dispatch-admission-boundary:
    owns:
      - squatch/daemon.py
      - tests/test_daemon_admission.py
    hooks: []
```

## Scope out
Do not wire production callers, scheduler/watcher, CLI verbs, background tasks, control requests, pause/kill behavior, durable dispatch accounting, config snapshotting, or a second pending queue. Preserve the existing production import closure. No existing test assertion changes. Production activation belongs to scheduler-activation.

## Scope fence
- squatch/daemon.py
- tests/test_daemon_admission.py

## Acceptance criteria
- `tests/test_daemon_admission.py` directly exercises the real boundary in `squatch/daemon.py`: one accepted offer invokes its work callback exactly once, a second offer while it is active is refused with zero callback calls, and maximum concurrent work is one. Event barriers prove reservation before the callback can yield; no elapsed-time sleeps establish correctness.
- `tests/test_daemon_admission.py` proves the active slot lasts through completion observation, and a subsequent offer succeeds after normal completion, a raised exception, and cancellation. The observer receives the original outcome; cancellation before the work coroutine starts also releases ownership without an unobserved task exception.
- `tests/test_daemon_admission.py` tests local admission behavior, not absence of production imports or CLI verbs, so its assertions survive scheduler activation. Record the construction-only dormancy evidence in the run record: scan the transitive local import closure rooted at `squatch/__main__.py`, recognizing both `import squatch.X` and `from squatch import X` as well as `from squatch.X import Y`; `squatch.daemon` must be unreachable, and an injected fixture edge to it must make that same scan fail. Do not commit a global negative assertion that a later activation's registry fence cannot migrate.
- `uv run pytest tests/test_daemon_admission.py tests/test_scheduler.py -q` exits 0, preserving the predecessor scheduler/watcher dormancy assertions.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_daemon_admission.py tests/test_scheduler.py -q
uv run pytest -q
```

## Definition of rejected
Stop if construction requires a production caller change or a path outside this registry fence, or if the boundary cannot prove single task ownership independently of scheduler activation.

## Time budget
- expected: 75m
- stuck: 150m
