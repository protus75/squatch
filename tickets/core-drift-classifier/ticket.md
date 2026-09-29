---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- core-renderer

## Context

## Plan contract
- section 20

## Goal
Add the dormant closed drift classification over managed host-file bytes.

## Why
Gate activation needs a pure, fully enumerated classification before any
production merge path can consume it.

## Scope in
Extend the merged `squatch/hostfiles.py` renderer and
`tests/test_hostfiles.py` with the pure closed classification
`missing | current | drifted | refused` over the renderer's bytes. Preserve
project-owned remainder and the renderer's refusal behavior. The classifier
makes no write and remains unreachable from production gates.

The predecessor-new module and test are deliberately excluded from
authoring-time Context; after `core-renderer` merges they are ordinary
worktree reads. There is no embedded Context and no on-demand exception.

## Scope out
Do not activate `core_drift`, edit gate or merge composition, write a host
file, or add another classification state.

## Scope fence
- squatch/hostfiles.py
- tests/test_hostfiles.py

## Acceptance criteria
- `tests/test_hostfiles.py` proves exactly the closed `missing | current | drifted | refused` classification.
- `tests/test_hostfiles.py` proves classification preserves project-owned remainder and inherits refusal for malformed, partial, and duplicate marker-like text.
- `tests/test_hostfiles.py` proves the classifier is pure, makes no write, and remains unreachable from production gates.

## Verification
```
uv run pytest tests/test_hostfiles.py -q
uv run pytest -q
```

## Definition of rejected
Reject an extra or ambiguous state, a classifier write, lost project-owned
bytes, permissive malformed markers, or production gate reachability.

## Time budget
- expected: 75m
- stuck: 150m
