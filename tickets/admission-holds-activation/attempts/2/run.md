## Outcome

premise_failed

## Surprises / judgment calls

Making the production control inbox an explicit, shared dependency requires every production `compose_pipeline` caller to provide it; constructing one inside merge composition would create the forbidden second inbox.

## Dead ends

The fenced implementation and scoped verification passed, but the required full-suite command fails at `tests/test_merge.py::test_compose_pipeline_builds_the_production_composition_from_config`: its unfenced call to `compose_pipeline` supplies no inbox. Updating that caller is required to remove the forbidden fallback, but `tests/test_merge.py` is outside the scope fence.

## Second problems filed


## Resolved engine/model

OpenAI Codex / GPT-5

## Predicted vs actual

Expected 75m; stopped after about 20m when the full-suite API caller outside the fence proved the contract could not be activated within scope.
