---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- phase5-exit

## Context

## Plan contract
- section 20

## Goal
Build the dormant managed-block renderer and its first-adoption behavior.

## Why
Phase 6 needs one deterministic owner for generated host conduct text before
drift can be classified or enforced.

## Scope in
Add new `squatch/hostfiles.py` and new `tests/test_hostfiles.py`. Implement
section 20's one managed-block renderer and first-adoption insertion. When a
host file contains zero marker-like text, insert the generated managed block
while preserving every project-owned byte. Malformed, partial, or duplicate
marker-like text refuses. Repeated rendering of the same content is
byte-idempotent.

Register the `core` CLI through existing `squatch/__main__.py` and preserve
the established CLI/parser contract through `tests/test_cli.py` and
`tests/test_verbs.py`. The renderer performs no Git operation and makes no
commit.

There is no embedded Context. The sibling-new module and test cannot be
Context, and the existing CLI registration paths are measured on-demand
inspection exceptions: `squatch/__main__.py` (30344 bytes),
`tests/test_cli.py` (24700 bytes), and `tests/test_verbs.py` (12471 bytes).
These authoring-time sizes are synthetic render fixtures and are never
compared with later live sizes.

## Scope out
Do not classify drift, activate a gate, edit Git state, commit a host file, or
add a second renderer or compatibility path.

## Scope fence
- squatch/hostfiles.py
- tests/test_hostfiles.py
- squatch/__main__.py
- tests/test_cli.py
- tests/test_verbs.py

## Acceptance criteria
- `tests/test_hostfiles.py` proves first adoption inserts exactly one generated managed block while preserving every project-owned byte.
- `tests/test_hostfiles.py` proves malformed, partial, and duplicate marker-like text refuse and repeated rendering is byte-idempotent.
- `tests/test_cli.py` and `tests/test_verbs.py` prove the `core` registration and existing parser/verb behavior.
- `tests/test_hostfiles.py` proves rendering performs no Git operation or commit.

## Verification
```
uv run pytest tests/test_hostfiles.py tests/test_cli.py tests/test_verbs.py -q
uv run pytest -q
```

## Definition of rejected
Reject a project-byte rewrite, permissive malformed marker handling,
non-idempotent output, an unregistered core verb, or any Git/commit effect.

## Time budget
- expected: 75m
- stuck: 150m
