## Outcome

premise_failed

## Surprises / judgment calls

The expanded composition caller fence is a measured on-demand Context partition;
embedding it exceeds the render bound while compact Context remains within headroom.

## Dead ends

The complete verification cannot pass inside the scope fence. The unchanged
`tests/test_seeded_phase3_10.py` renders `phase3-continue-11` at 120,420 characters
against the 120,000-character headroom limit; its inputs are unchanged from base,
and that test is outside this ticket's fence.

## Second problems filed

Pre-existing red: `tests/test_seeded_phase3_10.py::test_max_effort_renders_fit_with_pinned_authoring_material`.

## Resolved engine/model

OpenAI Codex, GPT-5.

## Predicted vs actual

Expected 75m; actual approximately 25m in this attempt.
