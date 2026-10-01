---
kind: bug
priority: P3
agent_tier: medium
agent_effort: medium
source: box:suggestion
state: draft
---

## Depends on
- none

## Context
- squatch/runner.py
- squatch/reconcile.py
- tests/test_terminal.py
- tests/test_reconcile.py

## Goal
`Runner._fault` in `squatch/runner.py` adds the faulted run's open `effect_intent` keys to its `Refusal` paved road, next to the stem and run it already names, by folding the journal with the existing `orphans` fold in `squatch/reconcile.py` -- no second fold. `reconcile()`'s `reconciled:` report line in `squatch/reconcile.py` also names `Orphan.open_keys` for the run it reaps, matching the `open_keys` the adjacent `log.event("reconcile", ...)` call already carries. When a run has no open key, both outputs stay exactly as they are today.

## Why
Plan section 11 states that a key left mid-effect by a dead run is reported with the key and the run that stranded it. Today only the run reaches the operator: `_fault`'s `Refusal` names the stem and `run_seq` but never the key, and `reconcile()`'s `reconciled:` report line names the stem and run while the open keys it already computed go only into the adjacent `log.event("reconcile", ..., open_keys=...)` call at reconcile.py:114 -- the engine log, not the stop message or the report the operator actually reads. `orphans()` in `squatch/reconcile.py` already folds the journal into exactly this fact (`Orphan.open_keys`) for every stranded stem; reusing that fold from `_fault` and surfacing the same field on the report line closes the gap without a second fold and without changing what reconcile does with the run (it still reaps it as `abandoned`).

## Scope in
- `Runner._fault` (squatch/runner.py): take a `journal: Journal` parameter, fold `orphans(journal.read())`, find the entry for `stem`, and when its `open_keys` is non-empty append the keys to the `Refusal` paved road alongside the existing `orphan` sentence; both call sites (`dispatch`, `_finish_delivery`) pass the `journal` already in their scope.
- The `reconciled:` `report(...)` call in `reconcile()` (squatch/reconcile.py): when `o.open_keys` is non-empty, name the keys in the report line alongside the stem and run it already names.
- Regression/unit tests in `tests/test_terminal.py` and `tests/test_reconcile.py` covering a fault raised between an `effect_intent` and its `effect_completion`.

## Scope out
- The `fault` log event `_fault` writes (`squatch/runner.py:498`, fields `ticket`, `run_seq`, `error`, `message`, `traceback`) is unchanged; it gains no `open_keys` field. The only existing engine-log record of open keys is `reconcile()`'s `log.event("reconcile", ..., open_keys=...)` at reconcile.py:114, which this ticket leaves as the log-side record and additionally surfaces on the report line.
- `orphans()`'s fold logic and the `Orphan` shape in `squatch/reconcile.py` are unchanged; this ticket calls the existing fold, it does not change it.
- Reconcile's disposition is unchanged: a stranded run is still reaped as `abandoned`.
- Any run with no open key: both the `Refusal` text and the `reconciled:` report line stay exactly as they are today.

## Scope fence
- squatch/runner.py
- squatch/reconcile.py
- tests/test_terminal.py
- tests/test_reconcile.py

## Acceptance criteria
- A fault raised between an `effect_intent` and its `effect_completion` produces a `Refusal` whose paved road names the stranded key and the run_seq, checked by `tests/test_terminal.py`.
- A fault raised with no open key produces the same `Refusal` text as today, unchanged, checked by `tests/test_terminal.py`.
- The next entry's reconcile pass's `reconciled:` report line for a run with an open key names that same key, checked by `tests/test_reconcile.py`.
- The `reconciled:` report line for an orphan with no open key is unchanged from today's wording, checked by `tests/test_reconcile.py`.

## Verification
```
pytest tests/test_terminal.py tests/test_reconcile.py -q
```

## Regression
```
pytest tests/test_terminal.py -k open_effect_key -q
```
- carries: tests/test_terminal.py

## Definition of rejected
Stop and throw the branch away if naming the key requires a second journal fold alongside `orphans`, requires widening `_fault`'s or `reconcile()`'s signature beyond threading the already-in-scope `journal`/`Orphan`, or requires adding a field to the `fault` log event -- this ticket surfaces an existing fold's existing field on two existing text outputs, nothing more.

## Time budget
- expected: 25m
- stuck: 50m
