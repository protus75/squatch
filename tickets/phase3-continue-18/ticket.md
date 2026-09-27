---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- storm-dispatch-hold

## Context
- tests/test_seeded_phase3_11.py
- tests/test_daemon_composition.py

## Plan contract
- section 20

## Goal
Author checkpoint push and the next shrinking continuation.

## Why
The production storm hold is complete; the next admission owns checkpoint durability through the existing Git seam.

## Scope in
Author only confirmed `checkpoint-push` and `phase3-continue-19` plus `tests/test_seeded_phase3_18.py`. Checkpoint push depends on `phase3-continue-18`; phase3-continue-19 depends on checkpoint-push. Both are medium/medium, use 75m/150m budgets and cap 3, cite section 20 alone, and derive fences as owns followed by hooks.

```yaml
ownership:
  checkpoint-push:
    owns:
    - squatch/checkpoint.py
    - tests/test_checkpoint.py
    hooks:
    - squatch/daemon.py
    - squatch/git.py
    - tests/test_git.py
    - tests/test_mergequeue.py
  phase3-continue-19:
    owns:
    - tickets
    - tests/test_seeded_phase3_19.py
    hooks: []
```

Checkpoint push has exact embedded Context `squatch/daemon.py`, `squatch/git.py`, and `tests/test_git.py`; `tests/test_mergequeue.py` is its sole fenced on-demand inspection exception for migrating the public-operation allowlist only. It owns a public argv-only Git push seam, composition through that seam, and re-firing an incomplete push after restart without duplicating a completed push. `squatch/checkpoint.py` and `tests/test_checkpoint.py` are new paths. Phase3-continue-19 has exact Context `tests/test_seeded_phase3_11.py` and `tests/test_daemon_composition.py`; the established seeded-test pattern exists at this admission, and sibling-new `tests/test_seeded_phase3_18.py` never enters Context.

Pin exact Context, every existing fence path as existing Context, new-path registry owners, authoring-time Context sizes, section 20's historical length, predecessor-test closure, and every max-effort render under `REQ_RENDER_HEADROOM`. Keep delimiter-bearing prompt-spec sources outside Context.

The finite ordered admissions are:
```yaml
[[checkpoint-push], [daemon-soak], [soak-run], [phase3-exit]]
```
The successor removes only the checkpoint-push row and carries exact suffix equality starting at daemon-soak. Do not author those future seeds now.

## Scope out
Do not implement checkpoint push, author daemon soak work, include sibling-new Context, or combine admissions.

## Scope fence
- tickets
- tests/test_seeded_phase3_18.py

## Acceptance criteria
- `tests/test_seeded_phase3_18.py` pins checkpoint-push and phase3-continue-19 identities, dependencies, medium/medium tiers, 75m/150m budgets, cap 3, owns-then-hooks fences, exact Context, registry owners, and render headroom.
- `tests/test_seeded_phase3_18.py` pins checkpoint's argv-only Git seam, restart re-fire behavior, exact Context, and `tests/test_git.py` fence.
- `tests/test_seeded_phase3_18.py` pins the continuation's established seeded-test Context, excludes sibling-new `tests/test_seeded_phase3_18.py`, and asserts exact successor suffix equality after removing only checkpoint-push.

## Verification
```
uv run pytest tests/test_seeded_phase3_18.py -q
uv run pytest -q
```

## Definition of rejected
Reject a missing Git seam test, sibling-new Context, an absent existing fence Context, combined admission, or a render over headroom.

## Time budget
- expected: 75m
- stuck: 150m
