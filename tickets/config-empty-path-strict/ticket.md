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
Loading a config fails with a `ConfigError` naming the offending dotted key whenever an empty string appears in any path or path-prefix field of the section 15 schema in `squatch/config.py`: `state_dir`, `worktree_root`, `report_inbox`, each `context_files[i]`, each `review.surfaces[i].rules_doc`, each element of a list-form `trigger` on `review.mechanical[i]` and `review.surfaces[i]`, and each `merge.strategies[i].paths[j]`. One shared non-empty-string mechanism covers all of these fields in place; no second validation path is added alongside it. `tests/test_config.py` gains cases loading a config with `state_dir: ""`, with a `trigger` list containing `""`, and with a `paths` list containing `""`, each asserting the load is refused with the real dotted key named. Every config that loads today keeps loading unchanged.

## Why
`state_dir` and `rules_doc` are typed as bare `Path` (config.py:176, 106), and `Path("")` normalises to `Path(".")`: a blank `state_dir` silently makes the checkout root the engine's state dir, and the defaulted `worktree_root` becomes `./worktrees` (config.py:207-208) instead of raising. `Trigger` is `Literal["always"] | list[str]` (config.py:26) with no element-level check, and `Strategy.paths` only requires a non-empty list, not non-empty elements (config.py:118) -- a blank string in either acts as a prefix matching every path, so one empty entry silently widens a review trigger or merge strategy to the whole tree. That is fail-open where every other corner of this loader (explicit null, out-of-vocabulary value, unknown key) is fail-closed. `notify`'s field validator already refuses an empty argv string in this same file (config.py:197-203), so this closes the identical gap for path and path-prefix fields on existing precedent.

## Scope in
- A shared non-empty-string mechanism in `squatch/config.py`, applied to `state_dir`, `worktree_root`, `report_inbox`, each `context_files[i]`, each `review.surfaces[i].rules_doc`, each element of a list-form `trigger` on `Mechanical` and `Surface`, and each element of `Strategy.paths`, raising the same dotted-path `ConfigError` shape as every other refusal in the file.
- Regression coverage in `tests/test_config.py` proving the refusal for `state_dir`, an empty `trigger` list element, and an empty `paths` list element, each asserting the loader's real dotted `err.key`.

## Scope out
- `notify`'s existing empty-argv-string guard (already correct, left unchanged).
- `config-numeric-bool-strict`'s numeric/bool coercion work and `config-gate-code-vocab`'s gate-code vocabulary checks (separate open tickets).
- `host-contract-null-rule`'s documentation work (separate open ticket; no behavior change here).
- The `"always"` literal branch of `Trigger`, and any non-path `str` field.

## Scope fence
- squatch/config.py
- tests/test_config.py

## Acceptance criteria
- Loading a config with `state_dir: ""` raises `ConfigError` with `err.key == "state_dir"`, checked by `tests/test_config.py`.
- Loading a config with `worktree_root: ""` raises `ConfigError` with `err.key == "worktree_root"`, checked by `tests/test_config.py`.
- Loading a config whose `review.mechanical[0].trigger` is `[""]` raises `ConfigError` with `err.key == "review.mechanical[0].trigger[0]"`, checked by `tests/test_config.py`.
- Loading a config whose `review.surfaces[0].trigger` is `[""]` raises `ConfigError` with `err.key == "review.surfaces[0].trigger[0]"`, checked by `tests/test_config.py`.
- Loading a config with `review.surfaces[0].rules_doc: ""` raises `ConfigError` with `err.key == "review.surfaces[0].rules_doc"`, checked by `tests/test_config.py`.
- Loading a config whose `merge.strategies[0].paths` contains `""` raises `ConfigError` with `err.key == "merge.strategies[0].paths[0]"`, checked by `tests/test_config.py`.
- Loading a config with `report_inbox: ""` raises `ConfigError` with `err.key == "report_inbox"`, checked by `tests/test_config.py`.
- Loading a config whose `context_files` contains `""` raises `ConfigError` with `err.key == "context_files[0]"`, checked by `tests/test_config.py`.
- `tests/test_config.py::test_valid_config_parses_to_typed_values` and `tests/test_config.py::test_absent_keys_take_the_shipped_defaults` still pass unchanged, checked by `pytest tests/test_config.py -q`.

## Verification
```
pytest tests/test_config.py -q
```

## Regression
```
pytest tests/test_config.py -k empty_string -q
```
- carries: tests/test_config.py

## Definition of rejected
Stop and throw the branch away if closing this requires a second, separate validation path alongside the shared mechanism (one helper reused per field class is fine; a bespoke ad hoc check duplicated per field is not), or requires narrowing what non-empty `Path`/`str` values these fields already accept.

## Time budget
- expected: 30m
- stuck: 60m
