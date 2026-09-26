---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- dispatch-pause-boundary
- pause-resume-activation

## Context
- tests/test_seeded_phase3_core.py
- squatch/control.py
- squatch/daemon.py
- squatch/driver.py

## Plan contract
- section 20

## Goal
Author the first two kill boundaries and the next shrinking Phase 3 continuation.

## Why
Pause activation establishes control identity and decision ordering for independent kill construction.

## Scope in
Author confirmed `kill-signal-journal`, `kill-executor-abort`, and `phase3-continue-10` seeds plus `tests/test_seeded_phase3_09.py`. `kill-signal-journal` depends on `phase3-continue-09`; `kill-executor-abort` depends on `kill-signal-journal`; and `phase3-continue-10` depends on both. All three use medium/medium, 75m/150m budgets, and configured seeding cap 3. Derive each kill seed fence as its owns followed by its hooks.

The signal boundary directly proves an identity-bound kill decision is journaled by the lock holder before any cancellation mutation. The executor boundary directly proves cancellation reaches and unwinds the active Driver invocation, preserving cancellation propagation; worker stopping and failure suppression are later boundaries. Both are dormant construction, with no kill verb before kill-cli-activation. `squatch/__main__.py` is outside both kill fences.

Each kill seed's Context lists its existing hooked paths. Pin their authoring-time existing-size map, exact new-path owners, max-effort render headroom, and successor suffix equality. Include an established seeded-test pattern in continuation Context, and close over any existing predecessor contracts that are migrated. Sibling-new paths and delimiter-bearing prompt-spec sources stay outside Context. Do not add hooks beyond the exact ownership below.

The finite ordered admissions are:
```yaml
[[kill-signal-journal, kill-executor-abort], [kill-worker-stop, kill-failure-suppression],
  [kill-cli-activation], [heartbeat], [restart-timers], [flake-detection, flake-release],
  [journal-roll, storm-ledger], [storm-producer-wiring, storm-notification-activation],
  [storm-dispatch-hold], [checkpoint-push], [daemon-soak], [soak-run], [phase3-exit]]
```

```yaml
kill_ownership:
  kill-signal-journal:
    owns:
    - tests/test_kill_signal_journal.py
    hooks:
    - squatch/control.py
    - squatch/daemon.py
  kill-executor-abort:
    owns:
    - tests/test_kill_executor_abort.py
    hooks:
    - squatch/daemon.py
    - squatch/driver.py
  phase3-continue-10:
    owns:
    - tickets
    - tests/test_seeded_phase3_10.py
    hooks: []
```

```yaml
ownership:
  phase3-continue-09:
    owns:
    - tickets
    - tests/test_seeded_phase3_09.py
    hooks: []
```

## Scope out
Do not implement kill, author beyond phase3-continue-10, add a CLI hook before kill-cli-activation, or put sibling-new or delimiter-bearing prompt-spec sources in Context.

## Scope fence
- tickets
- tests/test_seeded_phase3_09.py

## Acceptance criteria
- `tests/test_seeded_phase3_09.py` pins exact identities, edges, tiers, budgets, cap 3, kill ownership, compact owns-then-hooks fences, existing predecessor closure and CLI exclusion.
- `tests/test_seeded_phase3_09.py` pins existing hooked Context paths and their authoring-time sizes, exact new-path owners, max-effort render headroom, and the successor suffix equal to these admissions with only the first row removed.

## Verification
```
uv run pytest tests/test_seeded_phase3_09.py -q
uv run pytest -q
```

## Definition of rejected
Stop if predecessor closure needs an unfenced path or the successor duplicates an admission.

## Time budget
- expected: 75m
- stuck: 150m
