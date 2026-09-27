---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- phase3-exit

## Context
- squatch/config.py
- squatch/seams.py
- squatch/serve.py
- tests/test_serve.py

## Plan contract
- section 20

## Goal
Activate the sole escalation transport through a distinct injectable
notification executor in the real `serve` composition.

## Why
Phase 3 already journals storm trips and integration-red-streak holds for
status, but push delivery must remain isolated from the one active-work process
executor and recover safely after a daemon restart.

## Scope in
Add `squatch/notify.py` and `tests/test_notify.py`. Add the distinct injectable
`Notifications.notify(argv)` seam to `squatch/seams.py`; its production wrapper
owns a private `SubprocessExec` and never receives or shares the active-work
`ProcessExec`. The wrapper executes only argv, never a shell or an assembled
command string, and reports a missing or non-zero notification command through
the existing daemon failure/status path without dropping the durable signal.

Close `config.notify` in `squatch/config.py` and `tests/test_config.py` as either
unset or a non-empty argv of non-empty strings. The notification reconciler
reads journaled `storm_trip` signals and `control_hold` signals whose trigger is
`integration_red_streak`. It renders the closed escalation and its pull-side
`resume` action, then invokes the configured argv through an `Effect`. Keys use
the durable trip or hold identity and the ticket plus event, not an attempt, so
replay never double-sends a completed notification. An intent without a
completion is retried conservatively by re-sending, because external delivery
cannot be observed.

Wire the reconciler into `Serve`: reconcile old signals at startup before
dispatch and again on every watcher poll so signals created after startup are
pushed. An unset `config.notify` warns once at startup, invokes no transport,
and leaves every escalation in its existing status-only behavior. The Serve
notification parameter is a keyword whose default means no transport and the
same status-only behavior, preserving direct non-production constructors.
The unchanged `eval/daemon_soak.py` caller therefore keeps working without a
notification dependency.

Use `squatch/__main__.py` as the real composition root: `_serve` constructs the
notification wrapper separately from the active-work executor and passes it
into `Serve`. `tests/test_serve.py` must prove the real `_serve` passes a non-default wrapper,
so the constructor default can never become the production
path. `squatch/__main__.py`, `tests/test_config.py`, and `tests/test_seams.py`
are fenced on-demand headroom exceptions and are deliberately not embedded
Context. Preserve `tests/test_daemon_soak.py` and
`tests/test_daemon_soak_runner.py` unchanged as preservation-only suites.

## Scope out
Do not add a notification CLI verb, reuse the active-work executor, poll an
external delivery service, notify for watchdog signals, alter storm or merge
producers, or add another escalation vocabulary.

## Scope fence
- squatch/notify.py
- squatch/config.py
- squatch/seams.py
- squatch/serve.py
- squatch/__main__.py
- tests/test_notify.py
- tests/test_config.py
- tests/test_seams.py
- tests/test_serve.py

## Acceptance criteria
- `tests/test_notify.py`, `tests/test_config.py`, and `tests/test_seams.py` prove the closed argv config, injectable `Notifications.notify(argv)` seam, private notification `SubprocessExec`, stable Effect keys, completed replay suppression, and conservative re-send after an unmatched intent.
- `tests/test_notify.py` and `tests/test_serve.py` prove startup-before-dispatch and every-poll reconciliation of old and new storm-trip and integration-red-streak signals, plus one unset warning and status-only behavior with no transport call.
- `tests/test_serve.py` proves the default notification keyword preserves direct callers with status-only behavior and the real `_serve` passes a non-default wrapper constructed separately from active work.
- `tests/test_daemon_soak.py` and `tests/test_daemon_soak_runner.py` remain green unchanged, proving the default does not break the soak composition while production `serve` never uses that default.

## Verification
```
uv run pytest tests/test_notify.py tests/test_config.py tests/test_seams.py tests/test_serve.py -q
uv run pytest tests/test_daemon_soak.py tests/test_daemon_soak_runner.py -q
uv run pytest -q
```

## Definition of rejected
Reject a shared active-work process executor, raw subprocess use outside the
seam, attempt-scoped notification identity, a missed startup signal, repeated
completed delivery, a required Serve constructor argument that breaks direct
callers, silent unset transport, or a production `_serve` using the default.

## Time budget
- expected: 75m
- stuck: 150m
