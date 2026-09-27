---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- kill-worker-stop
- kill-failure-suppression

## Context
- tests/test_seeded_phase3_core.py
- tests/test_kill_signal_journal.py
- tests/test_kill_executor_abort.py
- tests/test_daemon_tasks.py
- tests/test_control_cli.py
- tests/test_daemon_composition.py

## Plan contract
- section 20

## Goal
Author the singleton kill activation and the shrinking Phase 3 continuation.

## Why
The four kill boundaries must merge before their production activation can be authored against existing interfaces.

## Scope in
Author only confirmed `kill-cli-activation` and `phase3-continue-12` seeds plus `tests/test_seeded_phase3_11.py`. The singleton activation admission stays alone: `kill-cli-activation` depends on `phase3-continue-11`; `phase3-continue-12` depends on `kill-cli-activation`. Both use medium/medium and 75m/150m budgets within configured seeding cap 3. Derive each fence as its owns followed by its hooks below. Pin exact identities, edges, tiers, budgets, new-path owners, max-effort render headroom, and successor suffix equality.

The activation seed exposes kill through the existing control/daemon/driver/CLI composition, journaled by the sole lock holder before mutation and bound to the current lifecycle. It connects the proven executor abort, worker stop, and failure suppression boundaries and blocks further admission after kill. Prove the real in-process production composition in `tests/test_kill_cli_activation.py`; do not launch serve. Preserve pause/resume routing and the no-running-engine direct locked path. Migrate `test_kill_boundary_is_dormant_and_not_a_cli_verb` in `tests/test_kill_signal_journal.py` to activation evidence in the same change that exposes kill. Inspect all four predecessor kill test files after their merges; migrate any invalidated dormancy/local contracts within the named hooks and preserve their positive guarantees. Run all four in activation Verification, plus the read-only daemon tasks, control CLI, and composition suites.

Every existing activation fence path must be existing Context when the activation is authored. Additionally, kill-cli-activation's Context must include the existing `tests/test_daemon_composition.py` as read-only Context, not a fence entry, to establish the production harness interface. `tests/test_seeded_phase3_11.py` must assert that inclusion and exclusion from the fence and keep the activation's max-effort render within `REQ_RENDER_HEADROOM`. The structured read-only Context requirement below is part of this authoring contract.

Use an established seeded-test pattern in continuation Context. Sibling-new paths and delimiter-bearing prompt-spec sources stay outside Context. This continuation reads the currently existing compact predecessor tests; the worker/failure sibling-new tests become activation Context only after they merge. Check predecessor-test closure and refuse any unfenced migration. Carry the finite admissions below; the successor removes only the head, starts at heartbeat, and neither repeats nor combines admissions.

```yaml
ownership:
  kill-cli-activation:
    owns:
    - tests/test_kill_cli_activation.py
    hooks:
    - squatch/control.py
    - squatch/daemon.py
    - squatch/driver.py
    - squatch/__main__.py
    - tests/test_kill_signal_journal.py
    - tests/test_kill_executor_abort.py
    - tests/test_kill_worker_stop.py
    - tests/test_kill_failure_suppression.py
  phase3-continue-12:
    owns:
    - tickets
    - tests/test_seeded_phase3_12.py
    hooks: []
read_only_context:
  kill-cli-activation:
  - tests/test_daemon_composition.py
```

The finite ordered admissions are:
```yaml
[[kill-cli-activation], [heartbeat], [restart-timers], [flake-detection, flake-release], [journal-roll,
    storm-ledger], [storm-producer-wiring, storm-notification-activation], [storm-dispatch-hold],
  [checkpoint-push], [daemon-soak], [soak-run], [phase3-exit]]
```

## Scope out
Do not implement kill behavior, author heartbeat in this admission, author beyond phase3-continue-12, or include sibling-new or delimiter-bearing sources in Context.

## Scope fence
- tickets
- tests/test_seeded_phase3_11.py

## Acceptance criteria
- `tests/test_seeded_phase3_11.py` pins exactly kill-cli-activation and phase3-continue-12, their dependency edges, medium/medium tiers, 75m/150m budgets, cap 3, owns-then-hooks fences, and new-path owners.
- `tests/test_seeded_phase3_11.py` asserts every existing fence path is existing Context, pins predecessor-test closure over all four kill tests, and ensures the activation migrates the kill-verb absence assertion while preserving the executor/worker/failure contracts.
- `tests/test_seeded_phase3_11.py` asserts tests/test_daemon_composition.py is read-only Context for kill-cli-activation, absent from its fence, and its max-effort render stays within REQ_RENDER_HEADROOM using pinned authoring-time Context sizes.
- `tests/test_seeded_phase3_11.py` pins the exact ordered suffix and successor equality after removing only [kill-cli-activation], leaving [heartbeat] first; no prior admission is duplicated or merged.

## Verification
```
uv run pytest tests/test_seeded_phase3_11.py -q
uv run pytest -q
```

## Definition of rejected
Stop if predecessor closure requires an unfenced path, render exceeds headroom, or the successor repeats an admission.

## Time budget
- expected: 75m
- stuck: 150m
