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
`squatch/config.py` parses config YAML through one shared `yaml.SafeLoader` subclass whose mapping constructor refuses a key that appears twice in the same mapping. Both `load()` and `migrate()` replace their `yaml.safe_load(text)` call with `yaml.load(text, Loader=<the shared SafeLoader subclass>)`, so an operator who writes `state_dir` twice, or repeats a key inside a nested block such as `providers[0].limits`, gets a `ConfigError` instead of a config where the last value silently wins. The finding names the repeated key by the same dotted path the other `ConfigError` findings use, for example `providers[0].limits.concurrency`. Tests in `tests/test_config.py` cover a repeated top-level key and a repeated nested key, each asserting the load is refused with the dotted path named on `err.key`. A config with no repeated keys loads exactly as it does today, and `migrate()`'s existing behavior (including `_schema_version_scalar`'s walk over the composed document) is unchanged except that it now only ever sees documents already guaranteed free of duplicate keys.

## Why
The loader is meant to fail closed: it already refuses unknown keys, explicit nulls, and wrong types. But `yaml.safe_load` at `squatch/config.py:310` and `:329` quietly keeps the last value when a mapping repeats a key. An operator who edits one copy of a repeated key and misses the other gets a config that reads right but runs with a different value, and nothing reports it. `migrate` depends on the same last-wins behavior today: `_schema_version_scalar` walks `reversed(document.value)` to find the `schema_version` node it rewrites. Refusing duplicates at the parser removes that ambiguity in both paths. No rendered ticket or decision covers duplicate keys; `config-numeric-bool-strict`, `config-gate-code-vocab`, and `host-contract-null-rule` cover type, vocabulary, and null checks, not YAML key uniqueness.

## Scope in
- A `yaml.SafeLoader` subclass in `squatch/config.py` whose overridden `construct_mapping` refuses a mapping that repeats a key, raising with the repeated key's dotted path (matching the `_nulls`/`_dotted` path style already used for other findings).
- Replacing both `load()`'s and `migrate()`'s `yaml.safe_load(text)` calls with `yaml.load(text, Loader=<that subclass>)`.
- Tests in `tests/test_config.py` proving the refusal for a repeated top-level key and a repeated nested key, and proving an ordinary config with no repeated keys still loads.

## Scope out
- Any YAML entry point other than `yaml.load` with the new `SafeLoader` subclass (no ruamel, no ad hoc duplicate-key pre-scan of the raw text).
- `migrate()`'s `yaml.compose(text)` call and `_schema_version_scalar`'s `reversed()` walk, left as they are.
- `config-numeric-bool-strict`, `config-gate-code-vocab`, `config-null-list-element`, and `host-contract-null-rule` (separate open tickets).

## Scope fence
- squatch/config.py
- tests/test_config.py

## Acceptance criteria
- Loading a config text with a top-level key repeated (for example `state_dir` written twice) raises `ConfigError` with `err.key == "state_dir"`, checked by `tests/test_config.py`.
- Loading a config text with a key repeated inside a nested mapping (for example `concurrency` repeated inside `providers[0].limits`) raises `ConfigError` with `err.key == "providers[0].limits.concurrency"`, checked by `tests/test_config.py`.
- `tests/test_config.py::test_valid_config_parses_to_typed_values` and `tests/test_config.py::test_absent_keys_take_the_shipped_defaults` still pass unchanged, checked by `pytest tests/test_config.py -q`.
- `tests/test_config.py::test_migrate_current_config_is_byte_identical_and_creates_no_backup` still passes unchanged, checked by `pytest tests/test_config.py -q`.

## Verification
```
pytest tests/test_config.py -q
```

## Regression
```
pytest tests/test_config.py -k duplicate -q
```
- carries: tests/test_config.py

## Definition of rejected
Stop and throw the branch away if closing this ticket requires a YAML parser other than PyYAML, or a loader that is not a `yaml.SafeLoader` subclass (for example `yaml.Loader`, `FullLoader`, or `UnsafeLoader`).

## Time budget
- expected: 30m
- stuck: 60m
