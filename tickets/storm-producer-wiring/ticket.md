---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- phase3-continue-16

## Context
- squatch/storm.py
- squatch/box.py
- squatch/daemon.py
- tests/test_storm.py
- tests/test_box.py
- tests/test_daemon_composition.py

## Plan contract
- section 20

## Goal
Construct a dormant journal-backed producer for every composed Box arrival.

## Why
Signature dedup counts reports; the storm ledger needs a durable identity for each arrival, including a signature-dedup hit.

## Scope in
Add an optional keyword `occurrence_recorder=` to Box, default None. Resolve the explicit non-None recorder first; otherwise resolve a scoped `contextvars.ContextVar` in `squatch/box.py` at enqueue time, including on Boxes constructed before scope entry. The scoped binding carries its state directory and cannot record arrivals from unrelated state directories. The resolution slot lives in box.py; box.py never imports daemon.py. The daemon owns installation through `daemon.compose_daemon_storm_producer(*, state_dir, journal, fs, clock)` over the already lock-held Journal. This is a synchronous context manager that spawns no tasks. Callers must await every task that inherited the binding before leaving the scope, including exceptional unwind. Reset the ContextVar token in finally; inactive-after-exit checks cover the current context only. Nested scopes restore the previous binding. No hidden task registry or manager-owned join is required.

This seam can reach Box construction sites in runner, stages, merge, triage, and author without editing those construction modules. Every box arrival here means the lock-holding engine's composed Box; unbound ordinary enqueue preserves existing behavior. Out-of-process `python -m squatch.box ingest` is out of scope for occurrence emission: it cannot inherit the binding or open another Journal under the engine lock.

Persist the box record first, including incrementing reports on a signature-dedup hit. Then call the recorder synchronously with `occurrence_id=<box_id>/<reports>`, `signature=message.signature`, and `emitting_stage=message.stage`. Keep `storm-occurrence/<signature>/<occurrence_id>` and the existing ledger body unchanged. A replay means re-recording the same persisted identity, not calling enqueue again: replay appends no second event; another enqueue is a new arrival and increments reports. a failed box write produces no occurrence; a recorder failure propagates with the box write durable for repair.

Before yielding the installed binding, reconcile every missing `<box_id>/<n>` for `1..reports`, regardless of resolution status, ordered by box seq then n. Each missing occurrence receives the append-time envelope timestamp from the Journal's injected clock; no historical timestamp can be reconstructed from the reports counter. Already-recorded occurrences keep their timestamps. Reconciliation is idempotent across journal segments and repeated scope entry. Test crash after durable box write but before ledger append, including several missing arrivals and a resolved record. Reset the token even if reconciliation fails on entry. The synchronous write/record sequence cannot interleave asyncio tasks; a single lock holder owns it, with no thread-safe or cross-process recorder contract.

Migrate only `test_production_import_closure_does_not_reach_the_dormant_ledger` in tests/test_storm.py from import absence to production composition remains dormant: daemon may import storm, but AST call-site reachability rooted at `squatch/__main__.py` and `squatch/drain.py` must show neither calls the producer hook or installs the binding. Keep the positive ledger contracts. New tests/test_storm_producer.py proves explicit and scoped recorders, cleanup and replay, and no trip signal, P0 report, notification, or dispatch hold. tests/test_box.py and tests/test_daemon_composition.py are read-only preservation suites, run unchanged.

## Scope out
No production activation, trip/report generation, dispatch suppression, new CLI verb, unscoped module-global recorder, or permanently installed recorder. Do not edit the Box construction modules or preservation tests.

## Scope fence
- tests/test_storm_producer.py
- squatch/storm.py
- squatch/box.py
- squatch/daemon.py
- tests/test_storm.py

## Acceptance criteria
- `tests/test_storm_producer.py` proves fresh and signature-dedup arrivals use distinct stable box-id/report-count identities, and replay appends no second event with the exact ledger key/body and stage.
- `tests/test_storm_producer.py` proves the synchronous context manager spawns no tasks; callers await every task that inherited the binding before leaving the scope, including exceptional unwind. The binding is inactive after normal and exceptional scope exit in the current context only, and nested scopes restore the previous binding; explicit recorders take precedence and other state directories do not leak into this journal.
- `tests/test_storm_producer.py` proves persisted-write-before-record ordering, recorder failure propagation, and reconciliation of every missing 1..reports identity with append-time Journal clock timestamps; it covers resolved records, repeated entry, rolled segments, and entry failure cleanup.
- `tests/test_storm.py` and `tests/test_storm_producer.py` prove dormant production composition, unchanged ledger window semantics, and absence of trips, reports and dispatch holds; `tests/test_box.py` and `tests/test_daemon_composition.py` pass unchanged.

## Verification
```
uv run pytest tests/test_storm_producer.py tests/test_storm.py tests/test_box.py tests/test_daemon_composition.py -q
uv run pytest -q
```

## Definition of rejected
Reject unstable replay identity, a journal write before the box write, a second writer, production activation, hidden task ownership, an unscoped module-global or permanently installed recorder, circular imports, or edits outside the fence.

## Time budget
- expected: 75m
- stuck: 150m
