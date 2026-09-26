---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- dispatch-pause-boundary

## Context
- tests/test_seeded_phase3_core.py
- squatch/daemon.py
- squatch/control.py
- squatch/mergequeue.py
- squatch/__main__.py
- tests/test_mergequeue.py
- tests/test_daemon_composition.py

## Plan contract
- section 20

## Goal
Activate pause/resume and merge admission holds with their release.

## Why
The constructed boundary needs a real production control path and releasable merge holds.

## Scope in
Wire pause/resume through the actual in-process production composition in `squatch/__main__.py` and `squatch/daemon.py`, using the existing control inbox. A live lock holder alone journals decisions; the CLI publishes lifecycle-bound requests without becoming a second journal writer. With no engine running, take the lock and apply directly. Pause precedes all durable dispatch accounting through the predecessor boundary, including its drain hook. Only resume releases the current hold, latest-wins.

Activate red-streak and tree-hash admission holds together with hold-instance-bound release. A red-streak hold fires at three consecutive distinct tickets going integration-red (K=3), resetting the streak on green; a tree-hash mismatch holds immediately. Neither cancels in-flight work. Journal before governed mutation, reject stale lifecycle or pre-hold releases, and preserve queue serialization and post-unwind Rework publication.

Migrate the construction dormancy contract in `tests/test_daemon_pause.py`, the literal no-pause/no-hold assertions in `tests/test_mergequeue.py`, and the production composition contracts in `tests/test_daemon_composition.py`. The daemon pause test is created by the dependency and is fenced but absent from authoring-time Context; read it after that dependency lands. Keep the no-serve contract: this ticket adds pause/resume, not serve. Own `tests/test_control_cli.py` for live-engine and no-engine CLI paths and use the real production composition harness to prove pause, release and both hold triggers. Preserve `tests/test_daemon_tasks.py` and `tests/test_control.py` unchanged as preservation-only suites, outside this fence and Context.

```yaml
ownership:
  pause-resume-activation:
    owns:
    - tests/test_control_cli.py
    hooks:
    - squatch/daemon.py
    - squatch/control.py
    - squatch/mergequeue.py
    - squatch/__main__.py
    - tests/test_daemon_pause.py
    - tests/test_mergequeue.py
    - tests/test_daemon_composition.py
```

## Scope out
Do not add kill or serve, change scheduler/watcher policy, or edit preservation-only suites.

## Scope fence
- tests/test_control_cli.py
- squatch/daemon.py
- squatch/control.py
- squatch/mergequeue.py
- squatch/__main__.py
- tests/test_daemon_pause.py
- tests/test_mergequeue.py
- tests/test_daemon_composition.py

## Acceptance criteria
- `tests/test_control_cli.py` proves pause/resume publication under a live engine lock and direct lock-held operation without an engine; stale identities and releases predating holds are ineffective.
- `tests/test_daemon_composition.py` proves real production pause/resume routing, non-preemption, and decision-before-mutation through the shared control boundary.
- `tests/test_mergequeue.py` proves red-streak and tree-hash holds block the next admission and matching resume releases them; serialization, re-gating, integration checks and Rework unwind remain correct.
- `tests/test_daemon_pause.py` migrates dormant activation assertions while retaining accounting-order tests; unchanged preservation-only suites pass.

## Verification
```
uv run pytest tests/test_control_cli.py tests/test_daemon_pause.py tests/test_mergequeue.py tests/test_daemon_composition.py tests/test_daemon_tasks.py tests/test_control.py -q
uv run pytest -q
```

## Definition of rejected
Stop if real composition or predecessor-test closure requires an unfenced path.

## Time budget
- expected: 75m
- stuck: 150m
