---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: high
agent_effort: high
---
## Depends on
- phase3-continue-11

## Context
- squatch/daemon.py
- tests/test_kill_signal_journal.py
- tests/test_kill_executor_abort.py
- tests/test_kill_worker_stop.py
- tests/test_kill_failure_suppression.py
- tests/test_daemon_composition.py

## Plan contract
- section 20

## Goal
Activate kill through the real bootstrap-drain composition.

## Why
The four independently proved kill boundaries can now meet at the production drain without claiming that the test-only DaemonTasks graph is production.

## Scope in
Add the `kill` CLI verb through the bootstrap drain's lock-held control path. The daemon seam owns the drain kill coordinator; the stage seam exposes only its existing Driver abort; the drain consumes control concurrently with an in-flight dispatch, latches stopping before a later admission or retry draw, and leaves the killed run terminal or restart-reconcilable before lock release. The CLI composition binds those seams. The lock holder journals a current-lifecycle decision before mutation and journals applied only after the active Driver has unwound. A stale request mutates nothing. With no engine running, `kill` takes the lock only to refuse `nothing running to kill`, creating no lifecycle, accepted decision, or stop latch. Preserve direct locked pause/resume.

Migrate only `test_kill_boundary_is_dormant_and_not_a_cli_verb` in `tests/test_kill_signal_journal.py` to activation evidence. Add `tests/test_kill_cli_activation.py` for real in-process drain composition; do not launch serve. Preserve the executor abort, worker stop, and failure suppression contracts as read-only evidence. Worker/failure activation remains deferred to the first real serve task owner; DaemonTasks is not production evidence.

The predecessor seed test's authoring-time byte counts are synthetic render fixtures, not live-size constraints on the four production files this activation must edit. Preserve unrelated documentation and typing; satisfy headroom with the compact kill changes rather than deleting existing prose.

## Scope out
Do not create serve, activate DaemonTasks worker-stop or failure-suppression boundaries, or change a predecessor contract other than the migrated kill-verb absence assertion.

## Scope fence
- tests/test_kill_cli_activation.py
- squatch/daemon.py
- squatch/stages.py
- squatch/drain.py
- squatch/__main__.py
- tests/test_kill_signal_journal.py

## Acceptance criteria
- `tests/test_kill_cli_activation.py` proves the production bootstrap drain consumes kill concurrently with its in-flight dispatch, latches stopping before later admission or retry draw, and reaches the active Stages-owned Driver abort.
- `tests/test_kill_cli_activation.py` proves the lock holder records accepted or stale decision before its governed mutation; accepted applied follows Driver unwind; a stale request mutates nothing; no-engine kill deterministically refuses without lifecycle or stop-latch state.
- `tests/test_kill_cli_activation.py` proves the real in-process drain composition without launching serve, and `tests/test_kill_signal_journal.py` migrates the kill-verb absence assertion to activation evidence.
- `tests/test_kill_executor_abort.py`, `tests/test_kill_worker_stop.py`, and `tests/test_kill_failure_suppression.py` remain explicit preservation evidence. Worker/failure activation is deferred to the first real serve owner.

## Verification
```
uv run pytest tests/test_kill_cli_activation.py tests/test_kill_signal_journal.py tests/test_kill_executor_abort.py tests/test_kill_worker_stop.py tests/test_kill_failure_suppression.py tests/test_daemon_tasks.py tests/test_control_cli.py tests/test_daemon_composition.py -q
uv run pytest -q
```

## Definition of rejected
Stop if control cannot reach the production Driver without an unfenced migration, if stopping permits a later admission or retry draw, or if the render exceeds headroom.

## Time budget
- expected: 75m
- stuck: 150m
