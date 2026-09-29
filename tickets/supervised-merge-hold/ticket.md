---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: high
agent_effort: high
---
## Depends on
- escape-column

## Context

## Plan contract
- section 20

## Goal
Hold a merge for supervised admission after all mechanical safety checks pass.

## Why
The escape-attribution boundary must merge before supervised admission can
preserve its terminal custody.

## Scope in
Implement durable HELD admission after merge safety and integration checks but before main mutation. Exclude held stems from dispatch while preserving their worktrees; release only through identity-bound `confirm` without a cap-rearming keep signal. Rebase and regate against moved main, migrate the daemon-soak passed-invoice reader to the candidate-base regate identity, reconstruct holds on restart, and never hold the bootstrap self-build. Every existing fenced path is a measured on-demand inspection exception; the new focused test is not Context.

## Scope out
Do not hold the bootstrap self-build, mutate main before the supervised release,
or construct a second admission path.

## Scope fence
- squatch/merge.py
- squatch/baseline.py
- squatch/control.py
- squatch/__main__.py
- squatch/stages.py
- squatch/drain.py
- squatch/runner.py
- eval/daemon_soak.py
- tests/test_merge.py
- tests/test_baseline.py
- tests/test_control_cli.py
- tests/test_cli.py
- tests/test_drain.py
- tests/test_daemon_soak_runner.py
- tests/test_supervised_merge_hold.py

## Acceptance criteria
- `tests/test_supervised_merge_hold.py` proves a durable HELD admission is recorded after merge safety and integration checks but before main mutation, preserves the worktree, and excludes the held stem from dispatch.
- `tests/test_supervised_merge_hold.py` proves only an identity-bound `confirm` releases the same hold without rearming a cap keep signal; stale identities do not release it.
- `tests/test_supervised_merge_hold.py` proves release rebases and regates against moved main, restart reconstructs held custody, and bootstrap self-builds are never held.
- `tests/test_daemon_soak_runner.py` proves the passed-invoice projection reads the candidate-base regate identity used by release.

## Verification
```
uv run pytest tests/test_merge.py tests/test_baseline.py tests/test_control_cli.py tests/test_cli.py tests/test_drain.py tests/test_daemon_soak_runner.py tests/test_supervised_merge_hold.py -q
uv run pytest -q
```

## Definition of rejected
Reject a pre-check hold, lost worktree, non-identity release, cap-rearming keep
signal, stale-main integration, unreconstructed restart custody, bootstrap hold,
or an edit outside the fence.

## Time budget
- expected: 75m
- stuck: 150m
