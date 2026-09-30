---
kind: chore
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
`tests/test_config.py` gains a test proving that when `load` is called with an explicit `path` AND a `config.yaml` also exists directly under `cwd`, the returned `Config` carries the explicit path's values, not the `cwd` file's. Production code in `squatch/config.py` is unchanged.

## Why
`load` in `squatch/config.py:300-302` reads `config.yaml` under `cwd` only when `path` is `None`. The existing `test_load_honours_an_explicit_config_path` (`tests/test_config.py:157-159`) passes a `cwd` that has no `config.yaml`, so it only catches a loader that ignores `path` entirely. It does not catch a loader that prefers the `cwd` file when both exist, which would quietly make an operator's `--config` flag lose to a stray `config.yaml` left in the working directory.

## Scope in
- One new test in `tests/test_config.py` that writes an explicit-path config and a distinct `config.yaml` at `cwd`, calls `load(path, cwd=cwd)`, and asserts the explicit file's value wins.

## Scope out
- Any change to `squatch/config.py`.
- Any change to load-path caching or cadence (covered by `decision-000043`).
- Any other config validation behavior (covered by `config-null-list-element`, `config-numeric-bool-strict`, `config-gate-code-vocab`).

## Scope fence
- tests/test_config.py

## Acceptance criteria
- A test in `tests/test_config.py` writes an explicit-path config with `state_dir: /tmp/squatch-explicit` and a separate `config.yaml` directly under `cwd` with `state_dir: /tmp/squatch-cwd`.
- That test calls `load(path, cwd=cwd)` and asserts the returned `Config.state_dir` equals `/tmp/squatch-explicit`, proving the explicit file wins over the `cwd` file's `config.yaml` when both exist.
- `squatch/config.py` has no changes, checked by `git diff --stat squatch/config.py` reporting no output.

## Verification
```
pytest tests/test_config.py -q
git diff --stat squatch/config.py
```

## Definition of rejected
Stop and throw the branch away if proving the precedence requires changing `squatch/config.py`'s behavior, or if the fixture's two configs cannot be made distinguishable through `state_dir` alone without touching production code.

## Time budget
- expected: 15m
- stuck: 30m
