---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- kill-cli-activation

## Context
- tests/test_seeded_phase3_core.py
- squatch/daemon.py
- tests/test_daemon_tasks.py
- tests/test_control_cli.py
- tests/test_daemon_composition.py

## Plan contract
- section 20

## Goal
Author heartbeat and the next shrinking Phase 3 continuation.

## Why
Kill activation closes the final kill admission, so heartbeat is next and its ownership must be repaired before it is passed forward.

## Scope in
Author confirmed `heartbeat` and `phase3-continue-13` seeds plus `tests/test_seeded_phase3_12.py`. `heartbeat` depends on `phase3-continue-12`; `phase3-continue-13` depends on `heartbeat`. Both use medium/medium, 75m/150m budgets, and configured seeding cap 3. Derive each fence as its owns followed by its hooks. Pin exact identities, edges, tiers, budgets, new-path owners, max-effort render headroom, and successor suffix equality.

`heartbeat.owns` is exactly new `squatch/heartbeat.py` and new `tests/test_heartbeat.py`; its only hook is existing `squatch/daemon.py`. `NEW_PATH_OWNERS` also maps new `tests/test_seeded_phase3_13.py` to `phase3-continue-13`. Heartbeat Context includes `squatch/daemon.py` and the selected existing daemon preservation tests `tests/test_daemon_tasks.py`, `tests/test_control_cli.py`, and `tests/test_daemon_composition.py`. Every existing fence path must be existing Context; sibling-new paths and delimiter-bearing prompt-spec sources stay outside Context.

Use the established seeded-test pattern in Context. Pin the selected predecessor-test closure, authoring-time Context sizes for the max-effort headroom render, and exclusion of sibling-new paths. Refuse an unfenced migration.

```yaml
ownership:
  heartbeat:
    owns:
    - squatch/heartbeat.py
    - tests/test_heartbeat.py
    hooks:
    - squatch/daemon.py
  phase3-continue-13:
    owns:
    - tickets
    - tests/test_seeded_phase3_13.py
    hooks: []
```

The finite ordered admissions are:
```yaml
[[heartbeat], [restart-timers], [flake-detection, flake-release], [journal-roll, storm-ledger],
  [storm-producer-wiring, storm-notification-activation], [storm-dispatch-hold],
  [checkpoint-push], [daemon-soak], [soak-run], [phase3-exit]]
```

## Scope out
Do not implement heartbeat, author beyond phase3-continue-13, include sibling-new paths in Context, or include prompt-spec sources containing the data-block delimiter.

## Scope fence
- tickets
- tests/test_seeded_phase3_12.py

## Acceptance criteria
- `tests/test_seeded_phase3_12.py` pins heartbeat and phase3-continue-13 identities, edges, medium/medium tiers, 75m/150m budgets, cap 3, owns-then-hooks fences, and new-path owners.
- It asserts every existing fence path is existing Context, pins the selected predecessor-test closure (`tests/test_daemon_tasks.py`, `tests/test_control_cli.py`, and `tests/test_daemon_composition.py`), and excludes sibling-new paths.
- `tests/test_seeded_phase3_12.py` pins authoring-time Context sizes and uses them to keep every max-effort render within `REQ_RENDER_HEADROOM`.
- `tests/test_seeded_phase3_12.py` pins the exact ordered successor suffix after removing only `[heartbeat]`, with no duplicated or combined admission.

## Verification
```
uv run pytest tests/test_seeded_phase3_12.py -q
uv run pytest -q
```

## Definition of rejected
Stop if predecessor closure needs an unfenced path, render exceeds headroom, or the successor duplicates an admission.

## Time budget
- expected: 75m
- stuck: 150m
