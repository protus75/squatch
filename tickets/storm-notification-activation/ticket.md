---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- storm-producer-wiring

## Context
- squatch/storm.py
- squatch/box.py
- squatch/daemon.py
- squatch/__main__.py
- tests/test_storm.py
- tests/test_box.py
- tests/test_daemon_composition.py

## Plan contract
- section 20

## Goal
Activate storm occurrence recording, replay-safe trip signals and one P0 failure report through the real production composition.

## Why
The dormant producer has a scoped binding that reaches every production Box without editing its construction sites.

## Scope in
Activate the scoped producer in `squatch/__main__.py` through the _RestartRunner session wrapper, after entering the existing lock-held session and before yielding it to run/drain work. Bind one producer to that session's state_dir, journal, fs and clock and leave it installed through work unwind; reset before the underlying Journal closes. Retain restart timer shutdown and lock ownership. The producer's synchronous context manager spawns no tasks; callers await every inherited task before leaving its scope, also on exceptional unwind. Use this call-time Box binding for every production construction reachable from drain/run: runner, stages, merge, triage, author. Test the harvest/second-problem path and the verification-attribution failure_report path with real production Box enqueue calls, including Boxes constructed before binding; daemon-only construction is not activation.

Consume the existing ledger's strict `K=5`, `T=1 hour` window. At each occurrence, identify a crossing from at most K to more than K live occurrences. The trip identity is deterministic over `(signature, first_live_occurrence_id, crossing_occurrence_id)`, using an unambiguous encoding and stable hash. Append one `signal` keyed `storm-trip/<trip_id>` carrying kind storm_trip, trip_id, signature, first_live_occurrence_id, crossing_occurrence_id and emitting_stage. The held-state intent is data only in this admission, with no control hold or dispatch mutation. Occurrences after the crossing while still above K cause no extra trip; a later fresh crossing may. An emitting_stage=None trip still reports but grants no global suppression.

For each trip store one P0 `failure_report` in the same state directory's durable Suggestion Box. Box records carry no priority field: preserve that contract and encode the P0 designation with exact origin `storm-breaker:P0:<trip_id>` and a P0 summary/detail naming the trip and its occurrence identities. Preserve the Message schema and ordinary enqueue arguments. Recover by exact-origin lookup across all statuses before enqueue, without incrementing reports for an already-present report; distinct trips cannot collapse because origin participates in the signature. The trip's own report is excluded from occurrence recording, including reconciliation, by the reserved storm-breaker origin namespace; this prevents recursive trips.

Unbound ordinary enqueue records nothing in the storm journal. Out-of-process CLI ingest is never a journal writer. In box.py, have CLI ingest acquire the same instance lock before mutating Box state and refuse deterministically with a paved road when the engine holds it; no concurrent reports-counter mutation. Unbound persisted arrivals are reconciled by the next composed lock holder under the producer's append-time rule.

Recover crossings by walking the complete ordered occurrence journal, including rolled segments, using each event's original envelope timestamp as now and the existing half-open window. This makes recovery deterministic even long after the crossing expires. Replay trips and repair missing reports on session entry, including a crash after occurrence append before trip creation and between trip signal and report enqueue. Existing trip keys and exact-origin reports are reused: replay cannot mint a second trip or increment report count. Both the live path and recovery use this same crossing rule. The reserved-report exclusion applies before reconciling Box counters so repair never feeds back into the ledger.

Migrate only producer/composition dormancy and no-trip/no-report assertions in tests/test_storm.py and tests/test_storm_producer.py; retain ledger and identity positives. tests/test_storm_producer.py is created by the depends-predecessor storm-producer-wiring and is sibling-new at authoring: it is a fenced migration target, never Context for this seed. Also migrate only `tests/test_drain.py::test_bootstrap_drain_never_scans_or_mutates_the_box`'s obsolete blanket assertion that no journal event contains `box`: keep its proof that drain neither mutates nor triages the pending Box record, while allowing the composed lock holder's required `storm_occurrence` reconciliation events. `tests/test_drain.py` is a fenced on-demand inspection exception rather than embedded Context because embedding the large suite breaches requisition headroom. tests/test_box.py and tests/test_daemon_composition.py are read-only preservation suites, run unchanged. There is no push transport in Phase 3: the journaled signal is the notification boundary.

Dispatch suppression stays exclusively in `storm-dispatch-hold`. tests/test_storm_notification_activation.py must exercise real drain work after a trip and prove dispatch still proceeds, with no storm control hold. Keep this dispatch-absence assertion available for the next seed to migrate.

## Scope out
No dispatch suppression, control hold/release, serve task owner, push transport, new Message priority field, construction-module edits, or unrelated test migration.

## Scope fence
- tests/test_storm_notification_activation.py
- squatch/storm.py
- squatch/box.py
- squatch/daemon.py
- squatch/__main__.py
- tests/test_storm.py
- tests/test_storm_producer.py
- tests/test_drain.py

## Acceptance criteria
- `tests/test_storm_notification_activation.py` proves the real __main__ run/drain session records arrivals from the harvest/second-problem and verification-attribution paths through the scoped producer, retaining lock, timer and exception cleanup behavior.
- `tests/test_storm_notification_activation.py` proves strict threshold, lower-bound expiry, same-window non-crossings, a later new crossing, and deterministic trip identity including emitting_stage=None.
- `tests/test_storm_notification_activation.py` proves exactly one trip signal and P0 failure_report per crossing across replay, resolved reports, rolled segments, occurrence-before-trip crashes, and trip-before-report crashes, without recursively recording reports or incrementing reports on recovery.
- `tests/test_storm_notification_activation.py` proves unbound enqueue makes no journal writes, CLI ingest refuses while the instance lock is held, and dispatch still proceeds after a trip with no storm control hold.
- `tests/test_storm.py` and `tests/test_storm_producer.py` migrate dormancy assertions while retaining positive ledger/producer tests; the named `tests/test_drain.py` test retains no-mutation/no-triage coverage while permitting storm reconciliation events; `tests/test_box.py` and `tests/test_daemon_composition.py` pass unchanged.

## Verification
```
uv run pytest tests/test_storm_notification_activation.py tests/test_storm_producer.py tests/test_storm.py tests/test_box.py tests/test_daemon_composition.py -q
uv run pytest tests/test_drain.py::test_bootstrap_drain_never_scans_or_mutates_the_box -q
uv run pytest -q
```

## Definition of rejected
Reject daemon-only construction, a second journal writer, unstable trip identity, duplicate reports on crash replay, recursive reports, new priority metadata, dispatch suppression, or edits outside the production fence.

## Time budget
- expected: 75m
- stuck: 150m
