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
- squatch/config.py
- tests/test_config.py

## Plan contract
- section 20

## Goal
Migrate the sole supported older configuration schema safely.

## Why
A host needs a deterministic, lossless transition from schema version 0 before
later Phase 6 work can rely on the current configuration shape.

## Scope in
Add only the explicit `migrate-config` verb. The sole supported older schema is
version 0: its complete key vocabulary, nesting, value types, defaults, and
meanings are exactly version 1's except for required top-level integer
`schema_version: 0`. The deterministic 0-to-1 mapping changes only that scalar
to integer 1 and keeps every other key byte-for-byte; it never resolves auth
values or changes host intent.

Validate the complete candidate through the real loader before one atomic
replace and retain a recoverable adjacent backup. A valid current version-1
file is a byte-identical no-op. Refuse with no write a missing or non-integer
version, a version below 0 or above 1, an unknown key, or input invalid under
the version-1 shape after scalar substitution. `squatch/__main__.py`,
`tests/test_cli.py`, and `tests/test_verbs.py` are measured on-demand
inspection exceptions; config and its focused test are Context.

## Scope out
Do not add another migration source, rewrite non-version bytes, resolve
credentials, or add a CLI verb other than `migrate-config`.

## Scope fence
- squatch/config.py
- squatch/__main__.py
- tests/test_config.py
- tests/test_cli.py
- tests/test_verbs.py

## Acceptance criteria
- `tests/test_config.py` proves version 0 changes only its integer schema scalar after real-loader validation and atomic replacement with adjacent backup.
- `tests/test_config.py` proves version 1 is byte-identical and every unsupported, malformed, unknown, or invalid candidate refuses without a write.
- `tests/test_cli.py` and `tests/test_verbs.py` prove the sole verb and all no-write boundaries.

## Verification
```
uv run pytest tests/test_config.py tests/test_cli.py tests/test_verbs.py -q
uv run pytest -q
```

## Definition of rejected
Reject a second supported legacy shape, a non-atomic or lossy migration, a
write on refusal, or any extra verb.

## Time budget
- expected: 75m
- stuck: 150m
