---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- phase2-exit

## Context
- eval/shakeout/bench.py
- squatch/seeds.py
- tests/test_seeds.py
- tests/test_terminal.py

## Plan contract
- section 20

## Goal
A dedicated end-to-end test proves that a merged seeding ticket registers and dispatches its confirmed successor through the real seed lift, intake, merge, and same-invocation drain rescan path.

## Why
Unit coverage of seed validation and a drain fixture that calls `Intake` by hand do not prove the self-hosted handoff. This proof crosses the real production-composed stages and admission: the parent Implement authors a successor, the parent's Check reviews and lifts those exact bytes, admission merges the parent, and the still-running drain discovers and runs the successor. It is test-only because all machinery already merged in Phase 2.

## Scope in
`tests/test_seed_successor.py` builds a disposable git checkout with the production `Runner` / `Drain` / `Pipeline` graph and scripted model seam in the established bench idiom. One committed confirmed seeder runs through Implement, authors exactly one confirmed successor ticket depending on the seeder, receives an approving per-seed requisition response and branch review, and merges. Without starting a second drain, the same invocation re-scans the committed ticket plane, dispatches the successor, and merges it. The proof reads the journal and git history to bind the successor bytes to the parent's passing requisition entry, `ticket_intake` signal, `seed_lift` signal, ticket-plane commit, and later `running` then `merged` transitions.

## Scope out
No production change, fake intake shortcut, direct journal fabrication, second drain invocation, hand commit of the successor, or assertion over a live external checkout. No new seed schema, lift path, rescan path, or report artifact.

## Scope fence
- tests/test_seed_successor.py

## Acceptance criteria
- In `tests/test_seed_successor.py`, one production-composed drain invocation runs a confirmed seeder whose scripted Implement authors one confirmed successor depending on it, merges the seeder, re-scans, and takes the successor through `running` and `merged` in that same invocation.
- In `tests/test_seed_successor.py`, the successor's committed `ticket.md` bytes match the passing per-seed requisition entry and the parent's `seed_lift` map, its `ticket_intake` signal names `source: seed`, `state: confirmed`, and the parent as seeder, and its ticket-plane commit precedes successor dispatch.
- In `tests/test_seed_successor.py`, the seeder branch diff contains only its ordinary code-lane fixture change while the successor ticket reaches main through a separate ticket-plane commit, proving no `tickets/**` file rode the parent's code branch.
- `uv run pytest tests/test_seed_successor.py -q` exits 0.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_seed_successor.py -q
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` if the proof requires changing production code, bypassing requisition review, fabricating an intake or lift signal, starting a second drain, widening the fence, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 60m
- stuck: 120m
