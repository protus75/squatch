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
- squatch/providers.py
- tests/test_config.py

## Goal
Loading a config whose `routing` list has two rows sharing the same `(tier, surface)` pair fails with a `ConfigError`. The raised error's `.key` names the later row's dotted path (for example `routing[3].surface`), and its message also names the earlier row's index (for example `routing[1]`) so the operator can see both colliding rows. The check is added to `Config._cross_references` in `squatch/config.py`, alongside the existing duplicate-provider-name check. `Registry` in `squatch/providers.py` is unchanged: it still builds `_routes` from a `routing` table that is now guaranteed to carry unique `(tier, surface)` keys. Every config that loads today with unique routing keys keeps loading unchanged.

## Why
`Registry.__init__` in `squatch/providers.py` builds `_routes` with a dict comprehension keyed by `(tier, surface)`, so when two `routing` rows share a key, the later row silently overwrites the earlier one in that map. An operator's earlier candidate list for that tier and surface is dropped with no signal, and routing then dispatches that tier and surface to providers the operator never chose for that slot. `_cross_references` already refuses a duplicate provider name (squatch/config.py:210-213) with an `_at`-wrapped `ValueError`; routing keys have no equivalent check. The fail-closed law requires this ambiguity to be refused at load time with a paved road (drop or merge one of the two rows), not silently resolved by dict insertion order, and putting the check next to the provider-name check keeps all routing-table validation in the loader's one path.

## Scope in
- A `(tier, surface)` duplicate check added to `_cross_references` in `squatch/config.py`, following the existing duplicate-provider-name pattern.
- A regression test in `tests/test_config.py` loading a config with two `routing` rows sharing one `(tier, surface)` pair.

## Scope out
- Any change to `Registry` or `_routes` construction in `squatch/providers.py`.
- Any change to the existing duplicate-provider-name check or the candidate-provider existence check already in `_cross_references`.

## Scope fence
- squatch/config.py
- tests/test_config.py

## Acceptance criteria
- Loading a config with two `routing` rows sharing one `(tier, surface)` pair raises `ConfigError` whose `.key` is the later row's dotted path, checked by `tests/test_config.py`.
- That `ConfigError`'s message names the earlier colliding row's index, checked by `tests/test_config.py`.
- Loading a config whose `routing` rows all have unique `(tier, surface)` pairs still loads unchanged, checked by `pytest tests/test_config.py -q`.

## Verification
```
pytest tests/test_config.py -q
```

## Regression
```
pytest tests/test_config.py -k duplicate_routing_key -q
```
- carries: tests/test_config.py

## Definition of rejected
Stop and throw the branch away if fixing this requires changing `Registry` or `_routes` construction in `squatch/providers.py`, changing the existing provider-name duplicate check or candidate-provider existence check, or touching any file outside `squatch/config.py`'s `_cross_references` and its dedicated test.

## Time budget
- expected: 20m
- stuck: 45m
