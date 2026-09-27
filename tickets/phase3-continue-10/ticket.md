---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- kill-signal-journal
- kill-executor-abort

## Context
- tests/test_seeded_phase3_core.py

## Plan contract
- section 20

## Goal
Author the next kill boundaries and the shrinking Phase 3 continuation.

## Why
Signal journaling and executor unwind establish the first kill boundaries; worker and failure policy remain independently provable work.

## Scope in
Author confirmed `kill-worker-stop`, `kill-failure-suppression`, and `phase3-continue-11` seeds plus `tests/test_seeded_phase3_10.py`. The worker boundary depends on phase3-continue-10, failure suppression depends on kill-worker-stop, and the continuation depends on both. All use medium/medium, 75m/150m budgets, and configured seeding cap 3. Derive each fence as its owns followed by its hooks. Pin exact identities, edges, tiers, budgets, new-path owners, max-effort render headroom, and successor suffix equality. Use an established seeded-test pattern as Context; Sibling-new paths and delimiter-bearing prompt-spec sources stay outside Context.

```yaml
ownership:
  kill-worker-stop:
    owns:
    - tests/test_kill_worker_stop.py
    hooks:
    - squatch/daemon.py
  kill-failure-suppression:
    owns:
    - tests/test_kill_failure_suppression.py
    hooks:
    - squatch/daemon.py
  phase3-continue-11:
    owns:
    - tickets
    - tests/test_seeded_phase3_11.py
    hooks: []
```

The finite ordered admissions are:
```yaml
- [kill-worker-stop, kill-failure-suppression]
- [kill-cli-activation]
- [heartbeat]
- [restart-timers]
- [flake-detection, flake-release]
- [journal-roll, storm-ledger]
- [storm-producer-wiring, storm-notification-activation]
- [storm-dispatch-hold]
- [checkpoint-push]
- [daemon-soak]
- [soak-run]
- [phase3-exit]
```

## Scope out
Do not implement kill behavior, author beyond phase3-continue-11, add a kill CLI verb before kill-cli-activation, or put sibling-new or delimiter-bearing prompt-spec sources in Context.

## Scope fence
- tickets
- tests/test_seeded_phase3_10.py

## Acceptance criteria
- `tests/test_seeded_phase3_10.py` pins worker/failure ownership, compact fences, edges, tiers, budgets, cap, new-path owners, headroom, and the shrinking suffix.

## Verification
```
uv run pytest tests/test_seeded_phase3_10.py -q
uv run pytest -q
```

## Definition of rejected
Stop if predecessor closure needs an unfenced path or the successor duplicates an admission.

## Time budget
- expected: 75m
- stuck: 150m
