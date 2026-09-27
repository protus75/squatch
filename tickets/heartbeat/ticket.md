---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- phase3-continue-12

## Context
- tests/test_seeded_phase3_11.py
- squatch/daemon.py
- tests/test_daemon_tasks.py
- tests/test_control_cli.py
- tests/test_daemon_composition.py

## Plan contract
- section 20

## Goal
Add the dormant heartbeat boundary for the daemon's watched core tasks.

## Why
An external watchdog needs one state-directory mtime that advances only while the watcher, merge, and box consumers are all live.

## Scope in
Add `squatch/heartbeat.py` and `tests/test_heartbeat.py`, and compose the heartbeat through `squatch/daemon.py`. The heartbeat file is `heartbeat` directly under the configured state directory. One explicit heartbeat pass writes the clock seam's current aware timestamp through the filesystem seam; it never calls the clock or filesystem directly outside those injected seams.

The heartbeat watches exactly the `DaemonTasks` watcher, merge, and box worker tasks. A pass writes only when all three have been started and none is done or failed. It skips the write before start, after clean stop or cancellation, and when any watched task has returned or raised. Construction through the daemon composition hook is dormant: it starts no task or loop and adds no `serve` CLI verb. Put the composition proof in the new fenced `tests/test_heartbeat.py`; keep the existing daemon preservation suites unchanged.

```yaml
ownership:
  heartbeat:
    owns:
    - squatch/heartbeat.py
    - tests/test_heartbeat.py
    hooks:
    - squatch/daemon.py
```

## Scope out
Do not add `serve`, start a heartbeat loop during construction, implement an external watchdog, or change the selected preservation suites.

## Scope fence
- squatch/heartbeat.py
- tests/test_heartbeat.py
- squatch/daemon.py

## Acceptance criteria
- `tests/test_heartbeat.py` proves the heartbeat path is `state_dir / "heartbeat"` and a live pass writes the injected aware clock value only through the injected filesystem seam.
- `tests/test_heartbeat.py` proves no write occurs before the three watched workers start, after they stop or are cancelled, or when any watcher, merge, or box task is done or failed.
- `tests/test_heartbeat.py` constructs the boundary through the `squatch/daemon.py` composition hook and proves construction starts no loop and adds no `serve` verb.
- `tests/test_daemon_tasks.py`, `tests/test_control_cli.py`, and `tests/test_daemon_composition.py` pass unchanged.

## Verification
```
uv run pytest tests/test_heartbeat.py tests/test_daemon_tasks.py tests/test_control_cli.py tests/test_daemon_composition.py -q
uv run pytest -q
```

## Definition of rejected
Stop if the heartbeat needs an unfenced migration or cannot remain dormant until a later real daemon loop owns its cadence.

## Time budget
- expected: 75m
- stuck: 150m
