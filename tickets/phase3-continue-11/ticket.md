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
- squatch/daemon.py
- squatch/stages.py
- squatch/drain.py
- squatch/__main__.py
- tests/test_kill_signal_journal.py
- tests/test_kill_executor_abort.py
- tests/test_kill_worker_stop.py
- tests/test_kill_failure_suppression.py
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
Author only confirmed `kill-cli-activation` and `phase3-continue-12` seeds plus `tests/test_seeded_phase3_11.py`. The singleton activation admission stays alone: `kill-cli-activation` depends on `phase3-continue-11`; `phase3-continue-12` depends on `kill-cli-activation`. The activation is KNOWN-DEEP and uses high/high; the continuation uses medium/medium. Both use 75m/150m budgets within configured seeding cap 3. Derive each fence as its owns followed by its hooks below. Pin exact identities, edges, tiers, budgets, new-path owners, max-effort render headroom, and successor suffix equality.

The activation seed exposes kill through the production bootstrap drain that exists now. The daemon seam owns a drain kill coordinator; the stage seam exposes only its existing Driver abort; the drain consumes control concurrently with an in-flight dispatch and latches stopping before any later admission or retry draw; the CLI composition binds those seams. The sole lock holder journals the current-lifecycle decision before mutation and does not journal applied until the active Driver has unwound. The killed run must be left terminal or restart-reconcilable before lock release. A stale request mutates nothing. With no engine running, `kill` takes the lock only to refuse `nothing running to kill`; it creates no lifecycle, accepted decision, or stop latch. Preserve direct locked pause/resume.

This activation does not pretend the test-only `DaemonTasks` graph is production. The worker-stop and failure-suppression boundaries remain dormant until a later real `serve` task owner activates them. Prove the real in-process drain composition in `tests/test_kill_cli_activation.py`; do not launch serve. Migrate `test_kill_boundary_is_dormant_and_not_a_cli_verb` in `tests/test_kill_signal_journal.py` to activation evidence in the same change that exposes kill. Preserve the other three predecessor kill suites unchanged as read-only Context and run them in Verification, along with the daemon tasks, control CLI, and composition suites.

Every existing activation fence path must be existing Context when the activation is authored. Additionally, kill-cli-activation's Context includes the three preservation-only predecessor tests and existing `tests/test_daemon_composition.py` as read-only Context, never fence entries. `tests/test_seeded_phase3_11.py` must assert those inclusions and exclusions and keep the activation's max-effort render within `REQ_RENDER_HEADROOM`. The structured read-only Context requirement below is part of this authoring contract.

The authored `phase3-continue-12` must repair the heartbeat contract now rather than pass the defect forward: `heartbeat.owns` is exactly new `squatch/heartbeat.py` and new `tests/test_heartbeat.py`; its hook is existing `squatch/daemon.py`; `NEW_PATH_OWNERS` also maps new `tests/test_seeded_phase3_13.py` to `phase3-continue-13`. Its Scope in names `squatch/daemon.py` and the existing daemon preservation tests it selects as heartbeat Context. Its acceptance criteria assert every existing fence path is existing Context, pin the selected predecessor-test closure, pin authoring-time Context sizes for the max-effort headroom render, and exclude sibling-new paths.

Use an established seeded-test pattern in continuation Context. Sibling-new paths and delimiter-bearing prompt-spec sources stay outside Context. This continuation reads the currently existing compact predecessor tests; the worker/failure sibling-new tests become activation Context only after they merge. Check predecessor-test closure and refuse any unfenced migration. Carry the finite admissions below; the successor removes only the head, starts at heartbeat, and neither repeats nor combines admissions.

```yaml
ownership:
  kill-cli-activation:
    owns:
    - tests/test_kill_cli_activation.py
    hooks:
    - squatch/daemon.py
    - squatch/stages.py
    - squatch/drain.py
    - squatch/__main__.py
    - tests/test_kill_signal_journal.py
  phase3-continue-12:
    owns:
    - tickets
    - tests/test_seeded_phase3_12.py
    hooks: []
read_only_context:
  kill-cli-activation:
  - tests/test_kill_executor_abort.py
  - tests/test_kill_worker_stop.py
  - tests/test_kill_failure_suppression.py
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
- `tests/test_seeded_phase3_11.py` pins exactly kill-cli-activation and phase3-continue-12, their dependency edges, activation high/high and continuation medium/medium tiers, 75m/150m budgets, cap 3, owns-then-hooks fences, and new-path owners.
- `tests/test_seeded_phase3_11.py` asserts every existing fence path is existing Context, pins predecessor-test closure over all four kill tests, migrates only the kill-verb absence assertion, and keeps executor/worker/failure contracts as explicit preservation evidence; it pins that worker/failure activation is deferred to the first real serve owner.
- `tests/test_seeded_phase3_11.py` asserts all four structured read-only paths are Context for kill-cli-activation and absent from its fence, and its max-effort render stays within REQ_RENDER_HEADROOM using pinned authoring-time Context sizes.
- `tests/test_seeded_phase3_11.py` pins the repaired heartbeat ownership, new-path owners, daemon Context, predecessor-test closure, and authoring-time Context-size/headroom requirements in the authored phase3-continue-12 ticket.
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
