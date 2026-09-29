---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- fixture-host-scaffold

## Context
- squatch/gates.py
- tests/test_gates.py

## Plan contract
- section 20

## Goal
Add the bug-ticket grammar and regression gate.

## Why
The fixture's planted regression needs a closed ticket and gate contract.

## Scope in
Add `kind: bug`, mandatory `## Regression`, and the branch-head-pass/merge-base-with-`carries`-overlay-fail hard gate. A missing test at base is never accepted as defect evidence. Existing `squatch/tickets.py`, `squatch/stages.py`, `tests/test_tickets.py`, and composition callers are measured on-demand inspection exceptions; the gate parser and focused `tests/test_gates.py` are Context.

## Scope out
Do not accept a missing base test as evidence or change paths outside the fence.

## Scope fence
- squatch/tickets.py
- squatch/gates.py
- squatch/stages.py
- tests/test_tickets.py
- tests/test_gates.py
- tests/test_bug_gate.py

## Acceptance criteria
- `tests/test_bug_gate.py` proves bug tickets require `kind: bug` and a `## Regression` section.
- `tests/test_bug_gate.py` proves the hard gate accepts a branch-head pass and rejects a merge-base failure reproduced with the `carries` overlay.
- `tests/test_bug_gate.py` proves a test absent at merge base is rejected as defect evidence.

## Verification
```
uv run pytest tests/test_bug_gate.py -q
uv run pytest tests/test_tickets.py tests/test_gates.py -q
uv run pytest -q
```

## Definition of rejected
Reject missing regression grammar, an unsound base comparison, or an edit outside the fence.

## Time budget
- expected: 75m
- stuck: 150m
