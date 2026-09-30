---
kind: bug
priority: P2
agent_tier: medium
agent_effort: medium
source: box:suggestion
state: draft
---

## Depends on
- none

## Context
- squatch/config.py
- tests/test_config.py

## Goal
Loading a config fails with a `ConfigError` whenever a YAML boolean is given for any `int` or `float` field anywhere in the section 15 schema: `providers[i].limits.concurrency`, `providers[i].limits.est_cost_per_call_usd`, `providers[i].limits.quota_window_minutes`, `scheduler.max_unmerged`, every `caps.*` field, `seeding.max_seeds_per_admission`, `circuit_breaker.k`, `circuit_breaker.cooldown_minutes`, `drain.max_runtime_hours`, and `drain.max_ticket_minutes`. The refusal names the offending key by the loader's real dotted path (for example `providers[0].limits.concurrency`), exactly like every other `ConfigError` finding. The fix is one shared mechanism on the `_Strict` base in `squatch/config.py` -- not a model-wide `ConfigDict(strict=True)`, which would also refuse the `str` values that `Path` fields (`state_dir`, `worktree_root`, `report_inbox`, `review.surfaces[*].rules_doc`) accept today.

## Why
Pydantic's lax coercion turns a YAML `true`/`false` into `1`/`0` for any numeric field, so a typo'd or mis-typed key loads as a real concurrency limit, cost, cap, or timeout instead of being refused. `squatch/config.py`'s own `schema_version` check already refuses a bool by hand (`parse()`, the `isinstance(version, bool)` guard before the integer check), which proves the engine already treats this as a real defect for one field; every other numeric field lacks the same guard. This breaks the fail-closed config contract the rest of the loader upholds (explicit-null refusal, closed vocabularies, unknown-key refusal).

## Scope in
- A shared before-validation mechanism on `_Strict` (or equivalent strict numeric annotations) in `squatch/config.py` that refuses `bool` for every `int`/`float` field, without narrowing what `Path` or `str` fields accept.
- Regression coverage in `tests/test_config.py` proving the refusal for the fields named in the Goal, using the existing `variant()`/`refused()` helpers and `err.key ==` assertions against the loader's real dotted paths.

## Scope out
- `schema_version`'s existing hand-written bool guard (already correct, left unchanged).
- Any `Path` or `str` field's coercion behavior.
- `config-gate-code-vocab`'s gate-code vocabulary checks and `host-contract-null-rule`'s documentation work (separate open tickets).

## Scope fence
- squatch/config.py
- tests/test_config.py

## Acceptance criteria
- Loading a config with `providers[0].limits.concurrency: true` raises `ConfigError` with `err.key == "providers[0].limits.concurrency"`, checked by `tests/test_config.py`.
- Loading a config with `providers[0].limits.est_cost_per_call_usd: true` raises `ConfigError` with `err.key == "providers[0].limits.est_cost_per_call_usd"`, checked by `tests/test_config.py`.
- The same boolean-refusal holds for `scheduler.max_unmerged`, every `caps.*` field, `seeding.max_seeds_per_admission`, both `circuit_breaker` fields, and both `drain` fields, each asserted by its own real dotted `err.key`, checked by `tests/test_config.py`.
- `tests/test_config.py::test_valid_config_parses_to_typed_values` and `tests/test_config.py::test_absent_keys_take_the_shipped_defaults` still pass unchanged, checked by `pytest tests/test_config.py -q`.
- A config using a `Path` field given as a plain string (for example `state_dir`) still loads, checked by `pytest tests/test_config.py -q`.

## Verification
```
pytest tests/test_config.py -q
```

## Regression
```
pytest tests/test_config.py -k boolean_numeric -q
```
- carries: tests/test_config.py

## Definition of rejected
Stop and throw the branch away if closing this requires flipping the model to `ConfigDict(strict=True)` (already probed to refuse valid `Path`-as-`str` values) or touching any field's accepted type other than rejecting `bool` on `int`/`float` fields.

## Time budget
- expected: 30m
- stuck: 60m
