---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- serve-activation

## Context
- tests/test_seeded_phase3_11.py
- tests/test_daemon_composition.py

## Plan contract
- section 20

## Goal
Author the deterministic daemon soak runner and the next shrinking continuation.

## Why
The merged serve composition supplies the production path from which the soak report must derive evidence.

## Scope in
Author only confirmed `daemon-soak-runner` and `phase3-continue-22` plus `tests/test_seeded_phase3_21.py`. `daemon-soak-runner` depends on `serve-activation`, is KNOWN-DEEP high/high, and owns `eval/daemon_soak.py`, `tests/test_daemon_soak.py`, and new `tests/test_daemon_soak_runner.py`. Its exact embedded Context is `tests/test_serve.py`, `eval/daemon_soak.py`, `tests/test_daemon_soak.py`, and `tests/test_audit.py`; `tests/test_restart_timers.py` and `tests/test_mergequeue.py` are on-demand fault-reference exceptions. `phase3-continue-22` depends on `daemon-soak-runner`, is medium/medium, owns `tickets` and `tests/test_seeded_phase3_22.py`, and has exact Context `tests/test_seeded_phase3_11.py` and `tests/test_serve.py`. Both cite section 20 alone, use 75m/150m budgets, stay within `drain.max_ticket_minutes`, and this admission stays within cap 3 with fences derived as owns followed by hooks.

```yaml
ownership:
  daemon-soak-runner:
    owns:
    - eval/daemon_soak.py
    - tests/test_daemon_soak.py
    - tests/test_daemon_soak_runner.py
    hooks: []
  phase3-continue-22:
    owns:
    - tickets
    - tests/test_seeded_phase3_22.py
    hooks: []
context:
  daemon-soak-runner:
  - tests/test_serve.py
  - eval/daemon_soak.py
  - tests/test_daemon_soak.py
  - tests/test_audit.py
  phase3-continue-22:
  - tests/test_seeded_phase3_11.py
  - tests/test_serve.py
```

`daemon-soak-runner` adds the public deterministic runner and its test. It drives the merged production serve composition through injected seams for at least 24 injected hours; exercises exactly `worker_killed_mid_run`, `conflict_resolution_rungs`, and `semantic_conflict_integration_red`; derives each closed member field from that member's local run evidence; and returns `DaemonSoakReport` to the existing canonical writer without writing the committed report. Existing fence paths are embedded Context. Sibling-new `tests/test_daemon_soak_runner.py`, `tests/test_seeded_phase3_22.py`, and delimiter-bearing `squatch/specs.py` are excluded from Context.

`phase3-continue-22` later authors medium/medium no-code `soak-run` plus `phase3-continue-23`; `soak-run` depends on `daemon-soak-runner` and produces only `tickets/soak-run/daemon-soak-report.json`. `phase3-continue-23` authors KNOWN-HARD high/high `phase3-exit` alone and no successor; the exit depends on `soak-run`, owns `tickets`, `tests/test_phase3_exit.py`, and `tests/test_seeded_phase4_core.py`, and reads the committed report with `daemon-soak-runner` as machinery and `soak-run` as producer. Pin each emitted seed's exact Context partition, on-demand exceptions, authoring-time Context sizes, predecessor-test closure, new-path owners, and max-effort `specs/implement.md` render under `RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM`.

The finite ordered admissions are:
```yaml
[[daemon-soak-runner], [soak-run], [phase3-exit]]
```
The successor removes only the daemon-soak-runner row and carries exact suffix equality starting at soak-run.

## Scope out
Do not implement serve, run the soak, author later suffix seeds now, include sibling-new or delimiter-bearing Context, or embed either on-demand fault reference.

## Scope fence
- tickets
- tests/test_seeded_phase3_21.py

## Acceptance criteria
- `tests/test_seeded_phase3_21.py` pins exact daemon-soak-runner and phase3-continue-22 identities, dependency edges, high/high versus medium/medium tiers, 75m/150m budgets, `drain.max_ticket_minutes`, cap 3, and exact owns-then-hooks fences.
- `tests/test_seeded_phase3_21.py` pins each emitted seed's exact Context partition, the two on-demand fault-reference exceptions, authoring-time Context sizes, predecessor-test closure, new-path owners, and exclusion of sibling-new paths and `squatch/specs.py` from Context.
- `tests/test_seeded_phase3_21.py` pins the exact corrected suffix `[[daemon-soak-runner], [soak-run], [phase3-exit]]`, exact successor suffix equality after removing only daemon-soak-runner, downstream owners/edges/tiers, member-local evidence and canonical-writer custody, and each max-effort render within `RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM`.

## Verification
```
uv run pytest tests/test_seeded_phase3_21.py -q
uv run pytest -q
```

## Definition of rejected
Reject combined admissions, missing member-local evidence, a self-attested report, sibling-new Context, an embedded on-demand fault root, a missing render proof, or a successor after Phase 3 exit.

## Time budget
- expected: 75m
- stuck: 150m
