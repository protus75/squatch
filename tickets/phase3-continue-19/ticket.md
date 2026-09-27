---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- checkpoint-push

## Context
- tests/test_seeded_phase3_11.py
- tests/test_daemon_composition.py

## Plan contract
- section 20

## Goal
Author daemon soak and the next shrinking continuation.

## Why
Checkpoint push is complete; the remaining Phase 3 registry admits the daemon soak boundary alone.

## Scope in
Author only confirmed `daemon-soak` and `phase3-continue-20` plus `tests/test_seeded_phase3_19.py`. `daemon-soak` depends on `phase3-continue-19`, is KNOWN-DEEP high/high, and `phase3-continue-20` depends on `daemon-soak` and is medium/medium. Both cite section 20 alone, use 75m/150m budgets, cap 3, and derive fences as owns followed by hooks.

```yaml
ownership:
  daemon-soak:
    owns:
    - eval/daemon_soak.py
    - tests/test_daemon_soak.py
    hooks:
    - squatch/artifacts.py
  phase3-continue-20:
    owns:
    - tickets
    - tests/test_seeded_phase3_20.py
    hooks: []
```

Daemon soak registers the closed report through `squatch/artifacts.py`. Pin exact identities, dependency edges, high/high versus medium/medium tiers, 75m/150m budgets within `drain.max_ticket_minutes`, and the seeding cap. Pin every existing fence path as existing Context, every new path's registry owner, predecessor-test closure, authoring-time Context sizes, section 20's historical length, and each max-effort `specs/implement.md` render under `RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM`. Keep delimiter-bearing prompt-spec sources, including `squatch/specs.py`, outside Context. Exclude sibling-new paths from Context.

The finite ordered admissions are:
```yaml
[[daemon-soak], [soak-run], [phase3-exit]]
```
The successor removes only the daemon-soak row and carries exact suffix equality starting at soak-run. Do not author those future seeds now.

## Scope out
Do not implement daemon soak, include sibling-new or delimiter-bearing Context, combine admissions, or author soak-run.

## Scope fence
- tickets
- tests/test_seeded_phase3_19.py

## Acceptance criteria
- `tests/test_seeded_phase3_19.py` pins daemon-soak and phase3-continue-20 identities, dependency edges, high/high versus medium/medium tiers, 75m/150m budgets, `drain.max_ticket_minutes`, cap 3, and owns-then-hooks fences.
- `tests/test_seeded_phase3_19.py` pins every existing fence path as existing Context, new-path registry owners, predecessor-test closure, and exclusion of sibling-new paths and `squatch/specs.py` from Context.
- `tests/test_seeded_phase3_19.py` pins authoring-time Context sizes, section 20's historical length, each max-effort `specs/implement.md` render within `RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM`, and exact successor suffix equality after removing only daemon-soak.

## Verification
```
uv run pytest tests/test_seeded_phase3_19.py -q
uv run pytest -q
```

## Definition of rejected
Reject an unnamed batch, missing fence Context, sibling-new Context, absent registry owner, combined admission, or render over headroom.

## Time budget
- expected: 75m
- stuck: 150m
