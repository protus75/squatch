---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: high
agent_effort: high
---
## Depends on
- phase3-continue-05

## Context
- squatch/config.py
- squatch/daemon.py
- squatch/scheduler.py
- squatch/watcher.py
- squatch/__main__.py
- tests/test_scheduler.py
- tests/test_daemon_admission.py
- tests/test_daemon_config.py

## Plan contract
- section 20

## Goal
Activate the dormant scheduler and watcher through a named in-process production composition.

## Why
The first production composition must prove dispatch admission, configuration capture, and reprioritization together without starting a daemon.

## Scope in
Add `compose_daemon_dispatch` in `squatch/daemon.py` and call it from `squatch/__main__.py` using the loaded-config supplier and the existing `_locked` dispatch seams. It constructs `DispatchAdmission(config supplier) -> Scheduler(dispatch through admission) -> Watcher`; do not add a CLI verb. Add `tests/test_daemon_composition.py` as the reusable in-process harness and call `compose_daemon_dispatch` there without launching a long-running process. Drive one single-flight dispatch through that graph, prove watcher reprioritization and per-dispatch config capture, and migrate `test_scheduler_and_watcher_are_unreachable_from_the_production_root` to positive scheduler/watcher reachability. Add a positive assertion that `squatch.daemon` is in `_local_import_closure` for the real repository root. Preserve `test_dormancy_scan_recognizes_import_forms_and_fixture_daemon_edge`, `_assert_daemon_unreachable`, the direct scheduling fixtures, and all local dispatch contracts in `tests/test_daemon_admission.py` and `tests/test_daemon_config.py`.

```yaml
ownership:
  scheduler-activation:
    owns:
      - tests/test_daemon_composition.py
    hooks:
      - squatch/daemon.py
      - squatch/scheduler.py
      - squatch/watcher.py
      - squatch/__main__.py
      - tests/test_scheduler.py
      - tests/test_daemon_admission.py
```

## Scope out
Do not add `serve` or another CLI verb, start background consumers, add control verbs, activate merge or rework, or add holds.

## Scope fence
- squatch/daemon.py
- squatch/scheduler.py
- squatch/watcher.py
- squatch/__main__.py
- tests/test_scheduler.py
- tests/test_daemon_admission.py
- tests/test_daemon_composition.py

## Acceptance criteria
- `tests/test_daemon_composition.py` calls `compose_daemon_dispatch` in process and proves the production composition can be constructed without launching a long-running process or adding a CLI verb.
- `tests/test_daemon_composition.py` proves the constructed `DispatchAdmission -> Scheduler -> Watcher` graph drives dispatch through admission single-flight, watcher reprioritization, and per-dispatch configuration capture.
- `tests/test_scheduler.py` migrates `test_scheduler_and_watcher_are_unreachable_from_the_production_root` to positive production reachability.
- `tests/test_daemon_admission.py` adds positive real-repository reachability for `squatch.daemon` while retaining `test_dormancy_scan_recognizes_import_forms_and_fixture_daemon_edge`, `_assert_daemon_unreachable`, and its local dispatch contracts; `tests/test_daemon_config.py` remains unchanged.
- `tests/test_daemon_composition.py` is reusable by later merge and rework activation seeds.
- `uv run pytest tests/test_scheduler.py tests/test_daemon_admission.py tests/test_daemon_config.py tests/test_daemon_composition.py -q` exits 0.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_scheduler.py tests/test_daemon_admission.py tests/test_daemon_config.py tests/test_daemon_composition.py -q
uv run pytest -q
```

## Definition of rejected
Stop if `compose_daemon_dispatch` cannot be called from the production root and proved in process without adding a CLI verb, or if a predecessor assertion requires a path outside this fence.

## Time budget
- expected: 120m
- stuck: 180m
