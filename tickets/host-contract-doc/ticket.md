---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- migrate-config

## Context

## Plan contract
- section 20

## Goal
Publish the host contract required before the fixture host is admitted.

## Why
Hosts need a copyable, bounded contract before the fixture can prove it.

## Scope in
Create new `docs/host-contract.md` and `tests/test_host_contract.py`. Commit the section 15 host schema's copyable commented `review`/`merge` example, seam inventory, report-inbox contract, managed-file ownership rule, and migration/cutover steps; explicitly exclude foreign process-state adoption. No production-code write and no Context.

## Scope out
Do not implement a host, alter engine code, or adopt foreign process state.

## Scope fence
- docs/host-contract.md
- tests/test_host_contract.py

## Acceptance criteria
- `tests/test_host_contract.py` proves the documented schema example, seams, inbox, ownership, and cutover boundaries.

## Verification
```
uv run pytest tests/test_host_contract.py -q
uv run pytest -q
```

## Definition of rejected
Reject missing contract elements, production-code edits, or foreign state adoption.

## Time budget
- expected: 75m
- stuck: 150m
