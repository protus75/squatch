---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- host-contract-doc
- core-drift-activation

## Context

## Plan contract
- section 20

## Goal
Build the deterministic fixture host for the closed Phase 6 scenarios.

## Why
The later report, regression, and escape loops need a safe zero-spend host.

## Scope in
Create new `hosts/fixture/` and `tests/test_fixture_host.py`: a host-root config profile, miniature deterministic app, replay-runner command, closed scenario list, bounded version-1 report fixtures, one merge-base regression defect, one machine-introduced escape scenario, and a scripted agent-CLI provider row serving Author/Implement/Review at zero model spend. Change no engine module; no embedded Context: sibling-new `docs/host-contract.md` is excluded at authoring and becomes an ordinary worktree read after `host-contract-doc` merges.

## Scope out
Do not change an engine module or embed the sibling-new host contract.

## Scope fence
- hosts/fixture/
- tests/test_fixture_host.py

## Acceptance criteria
- `tests/test_fixture_host.py` proves the deterministic profile, scenarios, bounded reports, regression, escape, and zero-spend provider row.

## Verification
```
uv run pytest tests/test_fixture_host.py -q
uv run pytest -q
```

## Definition of rejected
Reject an unbounded fixture, engine edit, missing scenario, or Context misuse.

## Time budget
- expected: 75m
- stuck: 150m
