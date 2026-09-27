## Outcome
premise_failed

## Surprises / judgment calls

Implemented session-scoped replay-safe storm trip reporting and exact-origin P0 report repair. The producer excludes its own storm-breaker reports from occurrence recording.

## Dead ends

`uv run pytest -q` fails in read-only `tests/test_drain.py::test_bootstrap_drain_never_scans_or_mutates_the_box`: its assertion requires no journal event contain `box`, but this ticket requires the next composed lock holder to reconcile unbound persisted Box arrivals, which necessarily appends `storm_occurrence` events with Box arrival identities. The conflicting test is outside the scope fence.

## Second problems filed


## Resolved engine/model

OpenAI Codex / GPT-5

## Predicted vs actual

Expected 75m; actual approximately 20m before the scope-fenced verification conflict.
