---
kind: bug
priority: P3
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
`parse()` in `squatch/config.py` (the validation path `load` uses) refuses a `schema_version` below `0` as an unsupported version, using the same classification `migrate-config` already applies, instead of routing it to the `migrate-config` paved road. Only `0` up to but not including `SCHEMA_VERSION` keeps the `migrate-config` road.

## Why
The loader's older-version branch (`version < SCHEMA_VERSION`, `squatch/config.py:286-289`) sends every lower integer, negative ones included, to `squatch migrate-config`. The merged `migrate-config` verb (`squatch/config.py:340-341`) refuses `version < 0` outright as an unsupported version. An operator whose config carries `schema_version: -1` is therefore sent to a verb that refuses them on arrival, breaking the fail-closed rule that every refusal ships a paved road that actually works. The loader's classification must match the verb's.

## Scope in
- The version check in `parse()` (`squatch/config.py:286-289`): split it so `version < 0` raises a `ConfigError` naming `schema_version` as unsupported without mentioning `migrate-config`, and `0 <= version < SCHEMA_VERSION` keeps today's `migrate-config` paved road unchanged.
- A regression test in `tests/test_config.py` proving the negative case.

## Scope out
- `migrate()`'s own `version < 0 or version > SCHEMA_VERSION` check (`squatch/config.py:340-341`) is unchanged.
- `SCHEMA_VERSION`'s value and every other config field are unchanged.

## Scope fence
- squatch/config.py
- tests/test_config.py

## Acceptance criteria
- Loading a config whose `schema_version` is `-1` raises a `ConfigError` whose finding key is `"schema_version"` and whose message does not contain `"migrate-config"`, checked by `tests/test_config.py`.
- Loading a config whose `schema_version` is `0` still raises a `ConfigError` whose message contains `"squatch migrate-config"`, checked by `tests/test_config.py`.
- Loading a config whose `schema_version` equals `SCHEMA_VERSION` still loads successfully, unchanged, checked by `tests/test_config.py`.

## Verification
```
python -m pytest tests/test_config.py -q
```

## Regression
```
python -m pytest tests/test_config.py::test_negative_schema_version_is_refused_without_migrate_config -q
```
- carries: tests/test_config.py

## Definition of rejected
Stop and throw the branch away if matching the negative case to `migrate-config`'s own classification requires changing `migrate()`'s behavior, widening the scope fence beyond `squatch/config.py` and `tests/test_config.py`, or introducing a third classification path alongside the two the plan already names -- this ticket is a two-branch split of one existing check, not a new validation scheme.

## Time budget
- expected: 20m
- stuck: 45m
