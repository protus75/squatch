---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- watchdog-detector

## Context
- squatch/watchdog.py
- squatch/notify.py
- squatch/serve.py
- tests/test_watchdog.py
- tests/test_notify.py
- tests/test_serve.py

## Plan contract
- section 20

## Goal
Activate the detector for the Stages-owned Driver on bootstrap drain and serve, including review.

## Why
Dormant construction must reach the real pipeline and deliver replay-safe escalation notifications.

## Scope in
Read the then-merged detector in squatch/watchdog.py before binding it. Install a
watchdog-owned LLM wrapper in squatch/watchdog.py where stages.compose constructs
the Stages LLMEffect. The wrapper implements call(req) and abort_current, forwards
on_event to CliClient.call, and delegates abort to that same client. Stages.run
supplies the per-run ticket and run_seq to the wrapper and clears that binding
on every exit. LLMEffect._call passes no on_event, Driver.__init__ takes no callback,
and LLMRequest has no run_seq: leave all three interfaces unchanged. The wrapper
routes around those constraints; no conditional keyword on the generic LLM seam.

compose_pipeline gains only an optional keyword, defaulting to unbound, forwarded
to stages.compose. Bind at construction in the drain/serve roots; never patch a
Pipeline after construction. Existing eval, merge, mergequeue, and daemon-composition
callers remain unchanged. eval/diagnose.py, eval/harness.py, eval/shakeout/bench.py,
and eval/shakeout/providers_group.py are non-production callers retaining optional on_event
behavior. The activation covers every call through the Stages-owned Driver,
including review, on bootstrap drain and serve. It does not claim every CliClient
in the repository. Keep FakeLLM.call and the LLM protocol unchanged.

Supply the detector's injected clock, current fence, serving-row USD cost basis,
flat estimate/metered flag, separate output-mutation observations through the
filesystem seam, and provider-cap wait intervals (empty when no wait occurs).
Preserve the existing hard-timeout abort/unwind path and process-group cleanup;
a soft trip never kills. Record durable signal bodies with kind: watchdog,
ticket (stem), spiral (spend_without_progress for soft; stuck for hard), and
run_seq (integer), with matching envelope ticket. Soft identity is
ticket + spiral + run_seq; stuck notification identity is ticket + stuck.
Append the signal before delivery; replay must not mint a new identity.

Extend NotificationReconciler._escalations for those two recognized identities;
use its Effect-backed transport with restart replay and unmatched-intent retry.
Serve keeps startup and each-poll reconciliation. _drain constructs config.notify's
SubprocessNotifications with a private process executor, separate from active work,
and invokes NotificationReconciler.reconcile at startup and after every dispatch.
Unset notify warns once and remains status-only on both paths; never pass provider
keys to the notification process. No notification owns or aborts the active executor.

Migrate tests/test_watchdog.py::test_watchdog_construction_has_no_production_callback_consumer
to a positive production-binding proof while preserving normalized collection and
the detector's direct behavior. Unconditionally migrate
 tests/test_notify.py::test_unrelated_signals_and_hold_release_do_not_notify:
retain proof that an unrecognized watchdog-kind body does not notify, and add
recognized soft/stuck identity delivery assertions. Preserve
 tests/test_providers.py::test_call_without_a_watchdog_consumer_keeps_the_existing_process_kwargs
and all stream/spool/redaction tests. tests/test_watchdog_activation.py proves
real drain and serve composition through the Stages-owned Driver with injected
process events and clock, review included; direct detector calls are insufficient.
It also owns drain startup and per-dispatch reconciliation proofs.

Context embeds serve.py and compact predecessor tests. These fenced on-demand
inspection exceptions must be read before editing, but would exceed the 120000
character REQ_RENDER_HEADROOM if all embedded: squatch/stages.py (55260),
squatch/drain.py (25709), squatch/__main__.py (19480), squatch/merge.py (29186),
squatch/providers.py (18687), tests/test_providers.py (32667),
tests/test_merge.py (33179), tests/test_mergequeue.py (46142).
providers.py is fenced for binding support only; changing CliClient.call is forbidden.
The two merge test suites may migrate assertions directly invalidated by the optional
composition keyword only; preserve all admission behavior.

Requisition review and author/triage roots (squatch/author.py, squatch/triage.py,
squatch/requisition.py), standalone diagnosis, and Serve's separate Rework driver
remain out of scope. File their watchdog binding to the Suggestion Box as a follow-up;
do not expand this fence. tests/test_serve.py and tests/test_daemon_soak.py preserve
real worker, kill, notification and soak behavior.

## Scope out
No detector redesign, new signals, cooldown/failover, reliability machinery, generic
LLM/Driver/LLMEffect signature change, or CliClient.call change. No edits to eval
callers, author/triage/requisition roots or the separate Rework driver. No soft kill
or post-construction Pipeline patch.

## Scope fence
- tests/test_watchdog_activation.py
- squatch/watchdog.py
- squatch/notify.py
- squatch/serve.py
- squatch/stages.py
- squatch/drain.py
- squatch/__main__.py
- squatch/merge.py
- squatch/providers.py
- tests/test_watchdog.py
- tests/test_providers.py
- tests/test_notify.py
- tests/test_serve.py
- tests/test_merge.py
- tests/test_mergequeue.py

## Acceptance criteria
- `tests/test_watchdog_activation.py` drives real bootstrap drain and serve composition, including Stages-owned review calls, through the wrapper; injected events, mutations, USD basis and cap waits reach the detector with the correct ticket/run_seq.
- `tests/test_watchdog_activation.py` proves healthy/no-page, one soft signal and notification per run, fresh-run notification, and stuck abort/unwind preservation with the specified signal bodies; soft trips never abort.
- `tests/test_watchdog_activation.py` proves drain startup and after-dispatch notification reconciliation, configured private transport and unset status-only behavior; `tests/test_serve.py` preserves startup/poll delivery and worker/kill behavior.
- `tests/test_watchdog.py` migrates the named dormancy assertion to positive production evidence while retaining detector/collector assertions; `tests/test_providers.py` preserves optional callbacks, spools, cleanup and redaction.
- `tests/test_notify.py` migrates the named unrelated-signal test unconditionally, preserves unrecognized watchdog-body exclusion, and proves recognized soft/stuck deduplication, replay and retry.
- `tests/test_merge.py`, `tests/test_mergequeue.py`, and `tests/test_daemon_soak.py` remain green with existing callers using the default unbound composition keyword.

## Verification
```
uv run pytest tests/test_watchdog_activation.py tests/test_watchdog.py tests/test_providers.py tests/test_notify.py tests/test_serve.py tests/test_daemon_soak.py tests/test_merge.py tests/test_mergequeue.py -q
uv run pytest -q
```

## Definition of rejected
Reject test-only binding, missed Stages review calls, invalidated dormancy tests left unchanged, a generic call signature change, duplicate pages, or an automatic soft kill.

## Time budget
- expected: 75m
- stuck: 150m
