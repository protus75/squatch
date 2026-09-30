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
Loading a config that has an explicit `null` as an element inside a list -- for example a `null` inside a verification argv list (`argv: [ruff, null]`) or inside a routing candidates list (`candidates: [null]`) -- fails with a `ConfigError` whose finding names the element's indexed dotted path (such as `routing[0].candidates[0]`) and states that an explicit null is refused, using a paved road that fits a list element (remove the element or replace it with a value) instead of pydantic's generic type-mismatch text.

## Why
`_nulls` in `squatch/config.py` walks the parsed config for explicit nulls before pydantic ever sees it. Its dict branch checks `v is None` and records a finding; its list branch (`squatch/config.py:268-270`) calls `_nulls(v, f"{prefix}[{i}]", out)` on every element with no such check, so a `None` element is neither a dict nor a list and produces no finding there. The load is still refused, but only later by pydantic's generic `Input should be a valid string` message, which doesn't carry the loader's own null-refusal wording and offers the mapping branch's "omit the key" road, which doesn't fit a list element. The rule that an explicit null is always refused should read the same regardless of where the null sits.

## Scope in
- The list branch of `_nulls` in `squatch/config.py`: report a `None` list element with its indexed dotted path and null-specific, list-fit wording.
- A regression test in `tests/test_config.py` loading a config with a `null` list element.

## Scope out
- The dict branch of `_nulls` (already correct, unchanged).
- Any change to `docs/host-contract.md` (covered by the separate `host-contract-null-rule` ticket).
- Any change to numeric/bool strictness or gate-code vocabulary validation (covered by `config-numeric-bool-strict` and `config-gate-code-vocab`).

## Scope fence
- squatch/config.py
- tests/test_config.py

## Acceptance criteria
- Loading a config with a `null` element inside a list (e.g. a verification argv list or a routing candidates list) raises `ConfigError` naming the element's indexed dotted path, checked by `tests/test_config.py`.
- That `ConfigError`'s finding uses the null-specific refusal wording with a paved road fit for a list element, not pydantic's generic type-mismatch text, checked by `tests/test_config.py`.

## Verification
```
pytest tests/test_config.py -q
```

## Regression
```
pytest tests/test_config.py -k null_list_element -q
```
- carries: tests/test_config.py

## Definition of rejected
Stop and throw the branch away if fixing this requires changing the dict branch's behavior or wording, changing pydantic's model schema, or touching any file outside `squatch/config.py`'s list branch of `_nulls` and its dedicated test.

## Time budget
- expected: 20m
- stuck: 45m
