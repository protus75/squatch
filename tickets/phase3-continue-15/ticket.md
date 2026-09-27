---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- flake-detection
- flake-release

## Context
- tests/test_seeded_phase3_11.py
- squatch/journal.py
- tests/test_journal.py

## Plan contract
- section 20

## Goal
Author journal roll, storm ledger, and the next shrinking Phase 3 continuation.

## Why
The flake pair closes its dormant ledger boundary; the next admission rolls the journal before building the storm occurrence ledger.

## Scope in
Author confirmed `journal-roll`, `storm-ledger`, and `phase3-continue-16` seeds plus `tests/test_seeded_phase3_15.py`. `journal-roll` depends on `phase3-continue-15`; `storm-ledger` depends on `journal-roll`; `phase3-continue-16` depends on both. All use medium/medium tiers, 75m/150m budgets, and the configured seeding cap 3. Cite section 20 alone. Derive each fence as owns followed by hooks.

```yaml
ownership:
  journal-roll:
    owns:
    - tests/test_journal_roll.py
    hooks:
    - squatch/journal.py
  storm-ledger:
    owns:
    - squatch/storm.py
    - tests/test_storm.py
    hooks: []
  phase3-continue-16:
    owns:
    - tickets
    - tests/test_seeded_phase3_16.py
    hooks: []
```

Journal roll owns the fixed 64 MiB/24h thresholds, ordered immutable segments, and preserved journal replay semantics. Storm ledger owns only the dormant occurrence ledger; producer wiring, notification activation, and dispatch hold remain separate later admissions.

Author storm ledger from section 20's storm-boundary clarification. Pin its exact `storm-occurrence/<signature>/<occurrence_id>` signal key and body, stable replay identity, cross-segment window fold, strict `count > K` result with shipped `K=5` and `T=1 hour`, lower-boundary expiry, and AST production-import dormancy. It emits no trip, box message, notification, or hold. Regenerate `phase3-continue-16` with explicit ownership, existing storm Context, predecessor migration/preservation classification, the production-root activation fence, and the clarification's exact sibling-new set.

Name each seed's exact Context, and name each new module's registry owner. Keep sibling-new paths, especially `squatch/storm.py`, outside sibling Context, and keep delimiter-bearing prompt-spec sources outside every Context. Pin every existing fence path is existing Context with no on-demand exceptions, authoring-time Context sizes, and every max-effort render within `REQ_RENDER_HEADROOM`; pin authoring-time section 20 length so later growth is not charged to historical fixtures.

For predecessor-test closure, classify `tests/test_journal.py` as read-only preservation for both journal-roll and storm-ledger and pin it in a `PRESERVATION` set, like the established seeded-test pattern. Require unchanged preservation verification; this ticket does not request a migration of that file.

Carry this exact ordered unseeded suffix:
```yaml
[[journal-roll, storm-ledger],
 [storm-producer-wiring, storm-notification-activation], [storm-dispatch-hold],
 [checkpoint-push], [daemon-soak], [soak-run], [phase3-exit]]
```
The successor removes only [journal-roll, storm-ledger]; no duplicated or combined admission, and no authoring beyond phase3-continue-16.

## Scope out
Do not implement roll or storms, author later admissions, include sibling-new paths in Context, or add retention/GC. Do not change existing journal tests.

## Scope fence
- tickets
- tests/test_seeded_phase3_15.py

## Acceptance criteria
- `tests/test_seeded_phase3_15.py` pins exact identities, dependencies, medium/medium tiers, 75m/150m budgets, cap 3, owns-then-hooks fences, exact Context, and the full new-path owner map.
- `tests/test_seeded_phase3_15.py`: Pin `journal-roll` depends on `phase3-continue-15`; `storm-ledger` depends on `journal-roll`; `phase3-continue-16` depends on both.
- `tests/test_seeded_phase3_15.py`: Pin every existing fence path is existing Context, no sibling-new paths or on-demand exceptions, authoring-time Context sizes, historical section 20 length, and each max-effort render within `REQ_RENDER_HEADROOM`.
- `tests/test_seeded_phase3_15.py`: Pin predecessor-test closure: `tests/test_journal.py` is read-only preservation for both journal-roll and storm-ledger, recorded in the `PRESERVATION` set and verified unchanged by both seeds.
- `tests/test_seeded_phase3_15.py`: Pin fixed 64 MiB/24h roll thresholds and the dormant storm-ledger boundary, leaving producer wiring, notifications, and dispatch hold in their separate admissions.
- `tests/test_seeded_phase3_15.py`: Pin section 20's exact storm occurrence identity, signal key/body, idempotence, cross-segment window result and AST import-closure dormancy, and require `phase3-continue-16` to carry the clarified existing-Context, production-root fence, and sibling-new rules.
- `tests/test_seeded_phase3_15.py`: Pin exact ordered successor suffix equality after removing only [journal-roll, storm-ledger], without duplication or combining admissions.

## Verification
```
uv run pytest tests/test_seeded_phase3_15.py -q
uv run pytest -q
```

## Definition of rejected
Stop if a render exceeds headroom, an existing fence path is absent from Context, a sibling-new path enters Context, or the successor duplicates or combines an admission. Report premise_failed and name the blocked path or admission.

## Time budget
- expected: 75m
- stuck: 150m
