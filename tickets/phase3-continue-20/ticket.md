---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- daemon-soak

## Context
- tests/test_seeded_phase3_11.py
- tests/test_daemon_composition.py

## Plan contract
- section 20

## Goal
Author production serve activation and the next shrinking continuation.

## Why
The first daemon-soak landing supplied schema, writer, and custody but exposed the missing production `serve` composition and deterministic report-producing runner. The corrected suffix must land those boundaries before the no-code run lane.

## Scope in
Author only confirmed `serve-activation` and `phase3-continue-21`, plus `tests/test_seeded_phase3_20.py`. `serve-activation` depends on `phase3-continue-20` and `daemon-soak`, is KNOWN-DEEP high/high, cites section 20 alone, uses 75m/150m budgets, and rides this admission alone. `phase3-continue-21` depends on `serve-activation`, is medium/medium with 75m/150m budgets, and owns the next ticket-plane admission. The batch stays within cap 3 and derives fences as owns followed by hooks.

```yaml
ownership:
  serve-activation:
    owns:
    - squatch/serve.py
    - squatch/daemon.py
    - squatch/__main__.py
    - tests/test_serve.py
    - tests/test_daemon_composition.py
    - tests/test_daemon_tasks.py
    - tests/test_kill_worker_stop.py
    - tests/test_kill_failure_suppression.py
    - tests/test_heartbeat.py
    - tests/test_storm.py
    hooks: []
  phase3-continue-21:
    owns:
    - tickets
    - tests/test_seeded_phase3_21.py
    hooks: []
```

The exact authoring-time embedded Context partitions are:
```yaml
context:
  serve-activation:
  - squatch/daemon.py
  - squatch/__main__.py
  - tests/test_daemon_composition.py
  - tests/test_daemon_tasks.py
  - tests/test_heartbeat.py
  - tests/test_storm.py
  phase3-continue-21:
  - tests/test_seeded_phase3_11.py
  - tests/test_daemon_composition.py
```

`serve-activation` adds the `serve` verb and production continuous loop, composes the existing dispatch, watcher, merge, box, control, heartbeat, restart/timer, storm, checkpoint, and worker-task boundaries, activates worker-stop and kill-failure-suppression, reconciles before dispatch, holds the writer lock for its lifetime, and exits only through kill/signal or terminal worker failure. Its test constructs the real production graph in-process, replaces the `serve`-absence assertions in `tests/test_daemon_composition.py` and `tests/test_heartbeat.py`, and migrates `tests/test_storm.py`'s production-root closure plus only invalidated predecessor dormancy assertions. The embedded Context is exactly `squatch/daemon.py`, `squatch/__main__.py`, `tests/test_daemon_composition.py`, `tests/test_daemon_tasks.py`, `tests/test_heartbeat.py`, and `tests/test_storm.py`. `tests/test_kill_worker_stop.py` and `tests/test_kill_failure_suppression.py` are fenced on-demand inspection exceptions because adding them breaches render headroom. New `squatch/serve.py` and `tests/test_serve.py` are sibling-new.

`phase3-continue-21` carries the corrected remaining admissions and authors `daemon-soak-runner` alone plus `phase3-continue-22`. The runner is KNOWN-DEEP high/high, depends on `serve-activation`, and owns `eval/daemon_soak.py`, `tests/test_daemon_soak.py`, and new `tests/test_daemon_soak_runner.py`. Its exact embedded Context is `tests/test_serve.py`, `eval/daemon_soak.py`, `tests/test_daemon_soak.py`, and `tests/test_audit.py`; `tests/test_restart_timers.py` and `tests/test_mergequeue.py` are on-demand fault-reference exceptions. Sibling-new `tests/test_daemon_soak_runner.py` and `squatch/specs.py` are excluded. It drives the merged production serve composition through injected seams for at least 24 injected hours and derives every closed member field from member-local evidence before returning a `DaemonSoakReport` to the existing writer. Its seeded test must pin the exact Context, on-demand exceptions, authoring sizes, predecessor closure, and max-effort render headroom. `phase3-continue-22` later authors medium/medium no-code `soak-run` plus `phase3-continue-23`; `soak-run` depends on `daemon-soak-runner` and produces only `tickets/soak-run/daemon-soak-report.json`. `phase3-continue-23` authors KNOWN-HARD high/high `phase3-exit` alone and no successor; the exit depends on `soak-run`, owns `tickets`, `tests/test_phase3_exit.py`, and `tests/test_seeded_phase4_core.py`, and reads the committed report with `daemon-soak-runner` as machinery and `soak-run` as producer.

The terminal admissions are:
```yaml
[[serve-activation], [daemon-soak-runner], [soak-run], [phase3-exit]]
```
Pin exact identities, edges, tiers, budgets, fences, embedded/on-demand Context partitions, new-path owners, predecessor-test closure, authoring-time Context sizes, the shrinking suffix, and each max-effort `specs/implement.md` render under `RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM`. The successor removes only the serve-activation row.

## Scope out
Do not implement serve, run daemon soak, author later suffix seeds now, embed the two on-demand production roots, or include sibling-new or delimiter-bearing prompt-spec sources in Context.

## Scope fence
- tickets
- tests/test_seeded_phase3_20.py

## Acceptance criteria
- `tests/test_seeded_phase3_20.py` pins exact `serve-activation` and `phase3-continue-21` identities, dependency edges, high/high versus medium/medium tiers, 75m/150m budgets, cap 3, and exact owns-then-hooks fences.
- `tests/test_seeded_phase3_20.py` pins the exact embedded production roots and predecessor tests, the two kill-test on-demand exceptions, new-path owners, predecessor-test closure, authoring-time Context sizes, and exclusion of sibling-new paths and `squatch/specs.py` from Context.
- `tests/test_seeded_phase3_20.py` pins the exact corrected suffix `[[serve-activation], [daemon-soak-runner], [soak-run], [phase3-exit]]`, exact successor suffix equality after removing only serve-activation, downstream owners/edges/tiers, and each max-effort render within `RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM`.

## Verification
```
uv run pytest tests/test_seeded_phase3_20.py -q
uv run pytest -q
```

## Definition of rejected
Reject a combined KNOWN-DEEP admission, missing production-serve boundary, missing member-local soak evidence, sibling-new Context, an embedded on-demand production root, or a successor after Phase 3 exit.

## Time budget
- expected: 75m
- stuck: 150m
