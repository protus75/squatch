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
- control-inbox

## Context
- tests/test_seeded_phase3_core.py
- squatch/daemon.py
- squatch/__main__.py
- tests/test_daemon_composition.py
- tests/test_mergequeue.py

## Plan contract
- section 20

## Goal
Author the pause-boundary pair and the next shrinking Phase 3 continuation.

## Why
Control intake and consumer lifetime ownership establish the independent pause activation boundary.

## Scope in
Author confirmed `dispatch-pause-boundary`, `pause-resume-activation`, and `phase3-continue-09` seeds plus `tests/test_seeded_phase3_08.py`. A later premise repair inserts human-authored `admission-holds-activation` between pause activation and `phase3-continue-09`: the boundary depends on `phase3-continue-08`, pause activation depends on the boundary, admission holds depend on pause activation, and the continuation depends only on admission holds. All use medium/medium and 75m/150m budgets; the original seed admission remains within configured cap 3. Derive each activation fence as its owns followed by its hooks. Pin the authoring-time existing-size map, exact new-path owners, max-effort render headroom, and successor suffix equality. The boundary hooks `squatch/drain.py` and `tests/test_drain.py` so pause precedes `_draw_retry`; pause activation hooks the lock-held `squatch/drain.py` session and migrates the daemon contracts, while admission holds separately hook the production merge composition and merge-queue contracts. Applicable preservation-only suites remain outside fences and Context. Sibling-new paths remain outside this continuation Context. The activation seeds include their now-existing fenced predecessor paths in Context except pause activation's `squatch/drain.py`, the explicit on-demand inspection exception required by render headroom.

```yaml
pause_ownership:
  dispatch-pause-boundary:
    owns:
      - tests/test_daemon_pause.py
    hooks:
      - squatch/daemon.py
      - squatch/control.py
      - squatch/drain.py
      - tests/test_drain.py
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
  admission-holds-activation:
    owns: []
    hooks:
      - squatch/mergequeue.py
      - squatch/merge.py
      - squatch/__main__.py
      - eval/shakeout/bench.py
      - tests/test_mergequeue.py
      - tests/test_merge.py
      - tests/test_daemon_composition.py
  phase3-continue-09:
    owns:
      - tickets
      - tests/test_seeded_phase3_09.py
    hooks: []
```

The finite ordered admissions are:
```yaml
- [dispatch-pause-boundary, pause-resume-activation]
- [kill-signal-journal, kill-executor-abort]
- [kill-worker-stop, kill-failure-suppression]
- [kill-cli-activation]
- [heartbeat]
- [restart-timers]
- [flake-detection, flake-release]
- [journal-roll, storm-ledger]
- [storm-producer-wiring, storm-notification-activation]
- [storm-dispatch-hold]
- [checkpoint-push]
- [daemon-soak]
- [soak-run]
- [phase3-exit]
```

## Scope out
Do not implement pause, author beyond phase3-continue-09, or put sibling-new or delimiter-bearing prompt-spec sources in Context.

## Scope fence
- tickets
- tests/test_seeded_phase3_08.py

## Acceptance criteria
- `tests/test_seeded_phase3_08.py` pins pause ownership, compact fences, edges, predecessor closure, preservation-only exclusions, size map, headroom, and shrinking suffix.
- `tests/test_seeded_phase3_08.py` pins `tests/test_mergequeue.py` and `squatch/__main__.py` as Context.

## Verification
```
uv run pytest tests/test_seeded_phase3_08.py -q
uv run pytest -q
```

## Definition of rejected
Stop if predecessor closure needs an unfenced path or the successor duplicates an admission.

## Time budget
- expected: 75m
- stuck: 150m
