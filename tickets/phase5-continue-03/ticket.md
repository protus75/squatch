---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- status-projection
- baseline-binding-reader

## Context
- tests/test_seeded_phase5_01.py

## Plan contract
- section 20

## Goal
Author the remaining finite Phase 5 admission boundary.

## Why
The two Phase 5 projections must settle before the doctor and terminal tail
are admitted.

## Scope in
Author only confirmed `retro-doctor-cli`, `phase5-continue-04`, and new
`tests/test_seeded_phase5_03.py`. The continuation embeds merged
`tests/test_seeded_phase5_01.py`, never its own new seeded test. Carry this
complete ordered registry:
```yaml
- [retro-doctor-cli, phase5-continue-04]
- [phase5-exit]
```
`retro-doctor-cli` starts medium/medium, cites section 20 alone, and owns
new `squatch/doctor.py`, new `tests/test_doctor.py`, plus `squatch/retro.py`,
`squatch/__main__.py`, `tests/test_retro.py`, `tests/test_cli.py`, and
`tests/test_verbs.py`. `retro-doctor-cli` depends on both `status-projection`
and `baseline-binding-reader`. `phase5-continue-04` depends on `retro-doctor-cli`,
owns only `tickets` and new `tests/test_seeded_phase5_04.py`, and embeds
merged `tests/test_seeded_phase5_02.py`, never its own test nor sibling-new
`tests/test_seeded_phase5_03.py`. `phase5-exit` is KNOWN-HARD high/high,
depends transitively on every Phase 5 stem, owns `tickets`, new
`tests/test_phase5_exit.py`, and new `tests/test_seeded_phase6_core.py`, and
has no successor.

The doctor ticket embeds `squatch/retro.py` (17745 bytes) and
`tests/test_retro.py` (20072 bytes). Its measured on-demand exceptions are
`squatch/__main__.py` (24624 bytes), `tests/test_cli.py` (19367 bytes), and
`tests/test_verbs.py` (9901 bytes). These are synthetic authoring-time sizes.
`tests/test_seeded_phase5_03.py` pins all ownership/context partitions and
the max-effort render headroom.

The authored `retro-doctor-cli` ticket carries section 20's complete feature
contract: the lock-held manual `retro` verb reuses the governed production
Retro path, while provider-free `doctor` performs only the five ordered
mechanical checks (`venv`, `git`, `config`, `lock`, `journal`). Its acceptance
criteria test verb behavior, exact output/exit classes, reads and write
boundaries in `tests/test_doctor.py`, `tests/test_retro.py`,
`tests/test_cli.py`, and `tests/test_verbs.py`; seed partition and synthetic
size assertions remain only in `tests/test_seeded_phase5_03.py`.

The authored `phase5-continue-04` ticket carries section 20's committed-
artifact Phase 5 exit disposition and exact Phase 6 core registry. It authors
only `phase5-exit`; its seeded proof pins the exit's clean-checkout retro,
scorecard, retro-provenance, and baseline reads plus the exact
`core-renderer`, `core-drift-classifier`, `phase6-continue` batch. It never
invents a Phase 6 name, owner, dependency, Context path, or exit read.
It also pins the compact-render correction: `phase5-exit`, all three Phase 6
core seeds, and every later Phase 6 seed cite section 20 alone; none renders
section 19. The continuation carries the finite Phase 6 rows now fixed in
section 20 and proves each max-effort render stays within headroom.

## Scope out
Do not implement a feature, use a same-admission seeded test as Context,
rename or reorder the registry, or add a successor after `phase5-exit`.

## Scope fence
- tickets
- tests/test_seeded_phase5_03.py

## Acceptance criteria
- `tests/test_seeded_phase5_03.py` pins the exact rows, edges, tiers, budgets, ownership, Context partition, synthetic sizes, and render headroom.
- `tests/test_seeded_phase5_03.py` proves `phase5-continue-04` uses merged `tests/test_seeded_phase5_02.py` and excludes both sibling-new seeded tests.
- `tests/test_seeded_phase5_03.py` proves `phase5-exit` is terminal, transitive, high/high, and owns its two new evidence paths.
- `tests/test_seeded_phase5_03.py` proves the doctor seed's feature criteria cover both verbs and leaves partition/size assertions in the seeded test only.
- `tests/test_seeded_phase5_03.py` proves the terminal continuation cites the closed Phase 5 exit disposition and Phase 6 core registry instead of inventing either boundary.
- `tests/test_seeded_phase5_03.py` proves the exit and Phase 6 seeds cite section 20 alone, never render section 19, carry section 20's fixed Phase 6 rows, and fit max-effort render headroom.

## Verification
```
uv run pytest tests/test_seeded_phase5_03.py -q
uv run pytest -q
```

## Definition of rejected
Reject an off-registry seed, an incorrect continuation fixture, an incomplete
doctor fence, or any successor after `phase5-exit`.

## Time budget
- expected: 75m
- stuck: 150m
