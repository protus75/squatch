---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- daemon-soak

## Context
- tests/test_seeded_phase3_11.py
- tests/test_daemon_composition.py

## Plan contract
- section 20

## Goal
Author the soak run and terminal Phase 3 continuation.

## Why
Daemon soak supplies the report machinery; the final admissions consume its ordinary-lane evidence.

## Scope in
Author only `soak-run` and `phase3-continue-21`, plus `tests/test_seeded_phase3_20.py`. Both are medium/medium, cite section 20 alone, use 75m/150m budgets within `drain.max_ticket_minutes`, cap 3, and derive fences as owns followed by hooks. The exact established Context is `tests/test_seeded_phase3_11.py` and `tests/test_daemon_composition.py`; `tests/test_seeded_phase3_19.py` and `tests/test_seeded_phase3_20.py` are sibling-new and never enter Context.

```yaml
ownership:
  soak-run:
    owns:
    - tickets/soak-run/daemon-soak-report.json
    hooks: []
  phase3-continue-21:
    owns:
    - tickets
    - tests/test_seeded_phase3_21.py
    hooks: []
  phase3-exit:
    owns:
    - tickets
    - tests/test_phase3_exit.py
    - tests/test_seeded_phase4_core.py
    hooks: []
```

`soak-run` depends on both `phase3-continue-20` and `daemon-soak`, changes no code, is fenced only to `tickets/soak-run/daemon-soak-report.json`, and produces that report through the ordinary lane. `phase3-continue-21` depends on `soak-run`, owns `tickets` plus `tests/test_seeded_phase3_21.py`, and authors `phase3-exit` alone and no successor. `phase3-exit` is KNOWN-HARD high/high, depends on `soak-run`, reads `tickets/soak-run/daemon-soak-report.json` against the schema owned by `squatch/artifacts.py`; `daemon-soak` is its machinery and `soak-run` its producer. It owns `tickets`, `tests/test_phase3_exit.py`, and `tests/test_seeded_phase4_core.py`.

The terminal admissions are:
```yaml
[[soak-run], [phase3-exit]]
```
Pin exact identities, edges, tiers, budgets, fences, Context partitions, new-path owners, predecessor-test closure, authoring-time Context sizes, the shrinking suffix, and each max-effort `specs/implement.md` render under `RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM`.

## Scope out
Do not run daemon soak, implement `soak-run`, author Phase 3 exit, or include sibling-new or delimiter-bearing prompt-spec sources in Context.

## Scope fence
- tickets
- tests/test_seeded_phase3_20.py

## Acceptance criteria
- `tests/test_seeded_phase3_20.py` pins exact `soak-run` and terminal Context partitions, identities, edges, tiers, budgets, fences, and new-path owners.
- `tests/test_seeded_phase3_20.py` pins exit-read closure, report producer/schema/machinery, predecessor-test closure, authoring-time sizes, and the seeding cap.
- `tests/test_seeded_phase3_20.py` pins the shrinking suffix, each max-effort `specs/implement.md` render, and no successor after `phase3-exit`.

## Verification
```
uv run pytest tests/test_seeded_phase3_20.py -q
uv run pytest -q
```

## Definition of rejected
Reject an unnamed or combined admission, a code change in soak-run, missing exit-read closure, sibling-new Context, or a successor after Phase 3 exit.

## Time budget
- expected: 75m
- stuck: 150m
