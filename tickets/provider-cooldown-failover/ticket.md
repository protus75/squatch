---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: high
agent_effort: high
---
## Depends on
- watchdog-activation

## Context
- squatch/providers.py
- squatch/timers.py
- tests/test_providers.py
- tests/test_restart_timers.py

## Plan contract
- section 20

## Goal
Fail over ordered configured providers after a classified cooldown without changing
the live provider registry.

## Why
Provider construction and activation are one registry payload: a cooldown must
remain restart-safe while an eligible configured candidate can keep work moving.

## Scope in
Implement provider cooldown failover only in the listed fence. At the provider seam,
classified CLI failures include quota exhaustion, which arms a journaled cooldown Timer using the injected
Clock; unrelated and unclassified failures retain their existing outcomes. Persist
the arm, re-arm it on restart, and journal `timer_fired` exactly when its window
resets. Use the existing Timer journal contract, with no side store or second timer
registry.

Provider construction and production activation use one registry/cooldown payload
in configured order. With a multi-candidate fixture, try configured candidates in order, skip a
candidate whose cooldown is live, and prove the served identity of the later
candidate. Keep the configured live provider set unchanged. A single configured candidate
that exhausts quota arms its cooldown and parks; it does not invent a
candidate. After the cooldown window resets, its journal records `timer_fired` and
it is eligible again.

Failover granularity is the attempt, never mid-call: a classified quota hit ends
that call without drawing the stem's infra cap, and a subsequent call selects the
next eligible configured candidate. When every candidate is cooling down, hold the
ticket without consuming `INFRA_CAP` until the journaled cooldown Timer fires.
Resolve each call exactly once across `WatchdogLLM` and its inner provider client;
both execution and watchdog cost/identity evidence use the same `Resolved` value,
including when a cooldown expires during the initial watchdog sample.

Each lock-held session has exactly one live journal-backed Timers instance. Both
bootstrap drain and daemon serve use the instance `_RestartRunner.session` creates
through `restart_session`/`compose_daemon_timers`; `Session` carries that same
payload into `Serve.compose`, and drain never constructs a second `Timers` instance
at its root. `stages.compose`/`compose_pipeline`, Serve's rework and triage clients,
and `__main__._triage_pass` receive the shared payload rather than constructing
independent registries. Migrate every fenced direct caller of `stages.compose`,
`compose_pipeline`, `Serve`, and `Session` to the required shared-payload signature.
Failover and cooldown therefore apply uniformly to implement, review, rework, and
triage calls.

The composition modules, their direct callers, and the large entry roots in the
fence are measured on-demand inspection exceptions: read them before editing, but
do not embed them because their authoring-time bytes would breach requisition
headroom. The direct provider and restart-timer suites are predecessor Context;
preserve their contracts and every other predecessor assertion while adding the new
direct failover suite.

## Scope out
Do not alter configured providers, add another registry payload or `Timers` lifetime,
implement reliability machinery, or turn a single-candidate cooldown into a
fabricated fallback. Do not preserve an independent-registry fallback for migrated
callers.

## Scope fence
- tests/test_provider_cooldown_failover.py
- squatch/providers.py
- squatch/watchdog.py
- squatch/timers.py
- squatch/runner.py
- squatch/restart.py
- squatch/daemon.py
- squatch/stages.py
- squatch/merge.py
- tests/test_providers.py
- tests/test_restart_timers.py
- tests/test_stages.py
- squatch/drain.py
- squatch/serve.py
- squatch/__main__.py
- eval/shakeout/bench.py
- eval/daemon_soak.py
- tests/test_serve.py
- tests/test_merge.py
- tests/test_mergequeue.py
- tests/test_daemon_composition.py

## Acceptance criteria
- `tests/test_provider_cooldown_failover.py` proves classified quota exhaustion arms and journals a cooldown Timer, unrelated and unclassified CLI failures keep their existing outcomes, restart re-arms the live deadline, and the injected Clock governs the window.
- `tests/test_provider_cooldown_failover.py` proves ordered multi-candidate failover with served-identity evidence, no change to the configured provider set, single-candidate parking without an invented candidate, and `timer_fired` on reset before renewed eligibility.
- `tests/test_provider_cooldown_failover.py` proves a quota-hit call draws no stem infra cap, later calls select the next eligible configured candidate without mid-call retry, all-candidates-cooling holds without repeated dispatch or `INFRA_CAP` consumption, and the ticket becomes dispatchable after `timer_fired`.
- `tests/test_provider_cooldown_failover.py` proves watchdog accounting and the inner client share one resolved served identity even when the selected candidate's cooldown expires during the initial watchdog sample.
- `tests/test_provider_cooldown_failover.py` proves one registry/cooldown payload and exactly one live journal-backed `Timers` instance exist per lock-held session; both drain and serve use the instance created by `_RestartRunner.session` through `restart_session`/`compose_daemon_timers`, `Session` carries it into `Serve.compose`, and drain creates no second instance at its root.
- `tests/test_provider_cooldown_failover.py` proves `stages.compose`, `compose_pipeline`, Serve's rework and triage clients, and `_triage_pass` receive the shared payload; every fenced direct caller of `stages.compose`, `compose_pipeline`, `Serve`, and `Session` supplies the required signature, with no independent registry fallback.
- `uv run pytest -q` proves all predecessor assertions remain valid except those explicitly migrated to the shared-payload contract, and production failover/cooldown covers implement, review, rework, and triage calls.

## Verification
```
uv run pytest tests/test_provider_cooldown_failover.py tests/test_providers.py tests/test_restart_timers.py tests/test_stages.py tests/test_serve.py tests/test_merge.py tests/test_mergequeue.py tests/test_daemon_composition.py -q
uv run pytest -q
```

## Definition of rejected
Reject an unclassified or mid-call failover, infra-cap consumption while a classified
cooldown is live, inconsistent watchdog/client served identity, a second registry payload or Timers lifetime, a
changed configured provider set, a fabricated single-candidate fallback, an
independent-registry compatibility path, or a cooldown reset without journaled
`timer_fired` evidence.

## Time budget
- expected: 75m
- stuck: 150m
