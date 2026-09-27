---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: high
agent_effort: high
---
## Depends on
- serve-activation

## Context
- tests/test_serve.py
- eval/daemon_soak.py
- tests/test_daemon_soak.py
- tests/test_audit.py

## Plan contract
- section 20

## Goal
Run the deterministic daemon soak through the merged production composition.

## Why
The daemon-soak schema and canonical writer are complete, but the corrected
Phase 3 suffix needs reproducible production evidence before the no-code
ordinary-lane producer can write its report.

## Scope in
Add `tests/test_daemon_soak_runner.py` and implement the public deterministic
runner in `eval/daemon_soak.py`, with its local report tests in
`tests/test_daemon_soak.py`. Drive the merged production `serve` composition
in-process through injected seams for at least 24 injected hours. Exercise exactly `worker_killed_mid_run`, `conflict_resolution_rungs`, and `semantic_conflict_integration_red`. For each closed report member, derive the
observed terminal/event, disposition, real producing run id, invariant-auditor
verdict, and green value from that member's local run evidence. Return the
`DaemonSoakReport` to the existing canonical writer, without writing the
committed report itself.

The exact embedded Context is `tests/test_serve.py`, `eval/daemon_soak.py`,
`tests/test_daemon_soak.py`, and `tests/test_audit.py`.
`tests/test_restart_timers.py` is the on-demand worker-reconcile fault
reference and `tests/test_mergequeue.py` is the on-demand two-rung and
integration-red fault reference. Production modules are on-demand read-only
inspection only. `tests/test_daemon_soak_runner.py` is sibling-new, and
delimiter-bearing `squatch/specs.py` is never Context.

## Scope out
Do not run the ordinary soak lane, write or self-attest the committed report,
modify production composition, embed either on-demand fault reference, or add
any scenario besides the three named scenarios.

## Scope fence
- eval/daemon_soak.py
- tests/test_daemon_soak.py
- tests/test_daemon_soak_runner.py

## Acceptance criteria
- `tests/test_daemon_soak_runner.py` proves the public runner drives the merged production serve composition through injected seams for at least 24 injected hours and exercises exactly the three named scenarios.
- `tests/test_daemon_soak_runner.py` proves every closed report member is derived from its own local run evidence, including terminal/event, disposition, producing run id, auditor verdict, and green value.
- `tests/test_daemon_soak.py` proves the runner returns `DaemonSoakReport` only to the existing canonical writer and never writes the committed report.

## Verification
```
uv run pytest tests/test_daemon_soak_runner.py -q
uv run pytest tests/test_daemon_soak.py -q
uv run pytest -q
```

## Definition of rejected
Reject a self-attested report, non-production composition, a wall-clock soak,
an unnamed scenario, shared rather than member-local evidence, or a direct
committed-report write.

## Time budget
- expected: 75m
- stuck: 150m
