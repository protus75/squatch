---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- restart-timers

## Context
- tests/test_seeded_phase3_11.py
- squatch/daemon.py
- squatch/__main__.py
- tests/test_control_cli.py
- tests/test_daemon_composition.py

## Plan contract
- section 20

## Goal
Author flake detection, flake release, and the next shrinking Phase 3 continuation.

## Why
Restart timers close the lifecycle boundary; the next paired admission detects flakes before releasing them.

## Scope in
Author confirmed `flake-detection`, `flake-release`, and `phase3-continue-15` seeds plus `tests/test_seeded_phase3_14.py`. `flake-detection` depends on `phase3-continue-14`; `flake-release` depends on `flake-detection`; `phase3-continue-15` depends on both flake seeds. Flake detection and release use medium/medium, 75m/150m budgets, and the configured seeding cap 3. Derive each fence as its owns followed by its hooks. Pin exact identities, edges, tiers, budgets, Context, new-path owners, max-effort render headroom, and successor suffix equality.

```yaml
ownership:
  flake-detection:
    owns:
    - squatch/flake.py
    - tests/test_flake.py
    hooks:
    - squatch/daemon.py
  flake-release:
    owns: []
    hooks:
    - squatch/flake.py
    - tests/test_flake.py
    - squatch/daemon.py
  phase3-continue-15:
    owns:
    - tickets
    - tests/test_seeded_phase3_15.py
    hooks: []
```

The full new-path owner map carries `squatch/restart.py`, `squatch/timers.py`, and `tests/test_restart_timers.py` as restart-timers paths; assigns flake paths to flake-detection; and assigns each seeded test to its continuation. Name each seed's exact Context. Sibling-new paths remain outside a sibling's Context and delimiter-bearing prompt-spec sources remain outside Context.

Author the flake pair from section 20's flake-boundary clarification, never from a SHA-held substitute. Detection folds `test_id`, `signature`, and the signature-deduped report `box_id` from `signal` key `flake/<box_id>` and body kind `flake_detected`; it writes no release record or release state. Release resolves that same entry through the box status's exact `fix_stem`, its merge, and the named test's green rerun; it appends `signal` key `flake-release/<box_id>/<fix_stem>` with kind `flake_released` and all four identity fields before folding the entry out. A second identical release is a no-event/no-state-change idempotent pass.

Both boundaries are dormant direct hooks composed in `squatch/daemon.py` and proven in fenced `tests/test_flake.py`. No production composition in `squatch/__main__.py` or `squatch/drain.py` calls or constructs them; import reachability through `squatch/daemon.py` is allowed. Existing daemon composition tests remain read-only preservation evidence, not a requested migration.

The finite ordered admissions are:
```yaml
[[flake-detection, flake-release], [journal-roll, storm-ledger],
  [storm-producer-wiring, storm-notification-activation], [storm-dispatch-hold],
  [checkpoint-push], [daemon-soak], [soak-run], [phase3-exit]]
```

## Scope out
Do not implement flakes, author beyond phase3-continue-15, include sibling-new paths in Context, or include prompt-spec sources containing the data-block delimiter.

## Scope fence
- tickets
- tests/test_seeded_phase3_14.py

## Acceptance criteria
- `tests/test_seeded_phase3_14.py` pins flake-detection, flake-release, and phase3-continue-15 identities, edges, medium/medium tiers, 75m/150m budgets, cap 3, owns-then-hooks fences, exact Context, and the full new-path owner map.
- `tests/test_seeded_phase3_14.py` pins flake-release depending on flake-detection and phase3-continue-15 depending on both flake seeds, while excluding sibling-new paths and on-demand Context exceptions.
- `tests/test_seeded_phase3_14.py` pins authoring-time Context sizes and keeps every max-effort render within `REQ_RENDER_HEADROOM`.
- `tests/test_seeded_phase3_14.py` pins the authoring-time section 20 length so later plan growth is not charged to this historical seed fixture.
- `tests/test_seeded_phase3_14.py` pins the test/report/fix-ticket identities, exact detection and release signal keys and bodies, append-before-removal ordering, second-release idempotence, and call-path dormancy; it rejects any SHA-held-set substitute.
- `tests/test_seeded_phase3_14.py` pins the exact ordered successor suffix after removing only `[flake-detection, flake-release]`, with no duplicated or combined admission.

## Verification
```
uv run pytest tests/test_seeded_phase3_14.py -q
uv run pytest -q
```

## Definition of rejected
Stop if a render exceeds headroom, an existing fence path is absent from Context, a sibling-new path enters Context, or the successor duplicates or combines an admission.

## Time budget
- expected: 75m
- stuck: 150m
