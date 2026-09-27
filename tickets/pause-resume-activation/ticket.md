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
- squatch/__main__.py
- tests/test_daemon_composition.py

## Plan contract
- section 20

## Goal
Activate pause/resume through the production daemon control boundary.

## Why
The constructed boundary needs a real production control path before any consumer can add releasable holds.

## Scope in
Wire pause/resume through the actual in-process production composition in `squatch/__main__.py` and `squatch/daemon.py`, using the existing control inbox. Inspect the fenced `squatch/drain.py` from the worktree and extend its public injection path so the inbox can be constructed from the journal inside its lock-held session; do not route through private drain methods or create a second journal writer. A live lock holder alone journals decisions; the CLI publishes lifecycle-bound requests without becoming a second journal writer. With no engine running, take the lock and apply directly. Pause precedes all durable dispatch accounting through the predecessor boundary, including its drain hook. Only resume releases the current hold, latest-wins.

Migrate the construction dormancy contract in `tests/test_daemon_pause.py` and the production composition contracts in `tests/test_daemon_composition.py`. The daemon pause test is created by the dependency and is fenced but absent from authoring-time Context; read it after that dependency lands. Keep the no-serve contract: this ticket adds pause/resume, not serve. Own and create the absent `tests/test_control_cli.py` before running Verification; it covers live-engine and no-engine CLI paths, including durable no-engine pause, stale lifecycle, pre-hold release, and live-lock publication without a second journal writer. Use the real production composition harness to prove routing, non-preemption, decision-before-mutation, restart rehydration, and matching release. Preserve `tests/test_daemon_tasks.py`, `tests/test_control.py`, and `tests/test_drain.py` unchanged as preservation-only suites, outside this fence and Context. Merge admission holds are the dependent `admission-holds-activation` ticket, not this boundary.

```yaml
ownership:
  pause-resume-activation:
    owns:
    - tests/test_control_cli.py
    hooks:
    - squatch/daemon.py
    - squatch/control.py
    - squatch/drain.py
    - squatch/__main__.py
    - tests/test_daemon_pause.py
    - tests/test_daemon_composition.py
```

## Scope out
Do not add kill or serve, change scheduler/watcher policy, or edit preservation-only suites.

## Scope fence
- tests/test_control_cli.py
- squatch/daemon.py
- squatch/control.py
- squatch/drain.py
- squatch/__main__.py
- tests/test_daemon_pause.py
- tests/test_daemon_composition.py

## Acceptance criteria
- `tests/test_control_cli.py` proves pause/resume publication under a live engine lock and direct lock-held operation without an engine; stale identities and releases predating holds are ineffective.
- `tests/test_daemon_composition.py` proves real production pause/resume routing, non-preemption, decision-before-mutation, restart rehydration, and matching release through the shared control boundary.
- `tests/test_daemon_pause.py` migrates dormant activation assertions while retaining accounting-order tests; unchanged preservation-only suites pass.

## Verification
```
uv run pytest tests/test_control_cli.py tests/test_daemon_pause.py tests/test_daemon_composition.py tests/test_daemon_tasks.py tests/test_control.py tests/test_drain.py -q
uv run pytest -q
```

## Definition of rejected
Stop if real composition or predecessor-test closure requires an unfenced path.

## Time budget
- expected: 75m
- stuck: 150m
