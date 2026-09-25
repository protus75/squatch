## Outcome
ok

## Surprises / judgment calls
The prior attempt's fence blocker no longer applied because `tests/test_drain_upgrade.py` is now explicitly in the scope fence. The existing edit-only premise release remains available while budget remains; once `premise_bounce` is spent, only an operator `confirm` releases it.

## Dead ends
An optional Ruff check could not run because Ruff is not installed in the project environment. All ticket verification commands passed.

## Second problems filed

## Resolved engine/model
OpenAI Codex; exact model identity not exposed.

## Predicted vs actual
Expected 60m; actual about 20m.
