---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- heartbeat

## Context
- tests/test_seeded_phase3_11.py
- squatch/daemon.py
- squatch/__main__.py
- tests/test_control_cli.py
- tests/test_daemon_composition.py

## Plan contract
- section 20

## Goal
Author restart timers and the next shrinking Phase 3 continuation.

## Why
Heartbeat supplies the liveness boundary that restart reaping and persistent timers follow.

## Scope in
Author only confirmed `restart-timers` and `phase3-continue-14` seeds plus `tests/test_seeded_phase3_13.py`. `restart-timers` depends on `phase3-continue-13`; `phase3-continue-14` depends on `restart-timers`. Restart-timers is KNOWN-DEEP and uses high/high; the continuation uses medium/medium. Both use 75m/150m budgets and the configured seeding cap 3. Derive each fence as its owns followed by its hooks below. Pin exact identities, edges, tiers, budgets, new-path owners, max-effort render headroom, and successor suffix equality.

Restart-timers reaps before dispatch and persists and re-arms timers. Treat `squatch/daemon.py` and `squatch/__main__.py` as the registry's exact daemon and CLI composition roots; both are existing Context, not on-demand exceptions. Use the existing control CLI and daemon composition tests as the selected predecessor-test closure. Do not add `squatch/drain.py` or any other inferred hook: if proving reap-before-dispatch requires that ungranted path, stop for a plan repair instead of inventing an exception.

Use `tests/test_seeded_phase3_11.py` as the established seeded-test pattern. Every existing fence path must be existing Context. Sibling-new paths and delimiter-bearing prompt-spec sources stay outside Context. Pin authoring-time Context sizes and keep every max-effort render within `REQ_RENDER_HEADROOM`.

```yaml
ownership:
  restart-timers:
    owns:
    - squatch/restart.py
    - squatch/timers.py
    - tests/test_restart_timers.py
    hooks:
    - squatch/daemon.py
    - squatch/__main__.py
  phase3-continue-14:
    owns:
    - tickets
    - tests/test_seeded_phase3_14.py
    hooks: []
```

The finite ordered admissions are:
```yaml
[[restart-timers], [flake-detection, flake-release], [journal-roll, storm-ledger],
  [storm-producer-wiring, storm-notification-activation], [storm-dispatch-hold],
  [checkpoint-push], [daemon-soak], [soak-run], [phase3-exit]]
```

## Scope out
Do not implement restart timers, author beyond phase3-continue-14, add an ungranted inspection exception, include `squatch/drain.py`, include sibling-new paths in Context, or include prompt-spec sources containing the data-block delimiter.

## Scope fence
- tickets
- tests/test_seeded_phase3_13.py

## Acceptance criteria
- `tests/test_seeded_phase3_13.py` pins restart-timers and phase3-continue-14 identities, edges, high/high and medium/medium tiers, 75m/150m budgets, cap 3, owns-then-hooks fences, and new-path owners.
- `tests/test_seeded_phase3_13.py` asserts every existing fence path is existing Context, pins `tests/test_control_cli.py` and `tests/test_daemon_composition.py` as predecessor-test closure, excludes sibling-new paths, and grants no on-demand inspection exception.
- `tests/test_seeded_phase3_13.py` pins authoring-time Context sizes and uses them to keep every max-effort render within `REQ_RENDER_HEADROOM`.
- `tests/test_seeded_phase3_13.py` pins the exact ordered successor suffix after removing only `[restart-timers]`, with no duplicated or combined admission.

## Verification
```
uv run pytest tests/test_seeded_phase3_13.py -q
uv run pytest -q
```

## Definition of rejected
Stop pending a plan fix if reap-before-dispatch needs `squatch/drain.py`, another unfenced path, or an on-demand Context exception; also stop if a render exceeds headroom or the successor duplicates an admission.

## Time budget
- expected: 75m
- stuck: 150m
