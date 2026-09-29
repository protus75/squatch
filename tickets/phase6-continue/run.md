## Outcome
premise_failed

## Surprises / judgment calls
The fixed `core-drift-activation` fence excludes `squatch/__main__.py`, where
the sole routing-to-conduct-file resolver lives. Recreating that resolver in a
fenced module would create a second path that can drift from `core`.

## Dead ends
`tests/test_hostfiles.py::test_classifier_is_unreachable_from_production_gates`
forbids any production module from importing or calling `classify`, but the
required hard `core_drift` gate must consume that classifier. Migrating that
predecessor assertion and fencing the routing seam require a section 20 change
outside this ticket's fence.

## Second problems filed

## Resolved engine/model
OpenAI Codex; serving model identity unavailable.

## Predicted vs actual
Expected 75m; actual about 5m.
