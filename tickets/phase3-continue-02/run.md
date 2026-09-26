## Outcome

ok

## Surprises / judgment calls

Kept `EXISTING_AT_AUTHORING` as synthetic render input and Context/fence membership data only, so future owner edits cannot invalidate this historical seed test. The Rework hook is a plain path list; its no-edit constraint remains Scope prose. Replaced the self-defining Rework outcome criterion with separate, observable update, split, escalation, approval-invalidation, and prompt-spec assertions.

## Dead ends

None.

## Second problems filed


## Resolved engine/model

codex / GPT-5

## Predicted vs actual

Expected 75m; actual about 20m. `uv run pytest tests/test_seeded_phase3_02.py -q` and `uv run pytest -q` passed.
