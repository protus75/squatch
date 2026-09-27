## Outcome
premise_failed

## Surprises / judgment calls
The repaired activation contract requires the exact bootstrap-drain fence and six-file embedded Context specified by section 20. The prior continuation's pinned test still requires the superseded broader fence and an incompatible Context ordering.

## Dead ends
`uv run pytest tests/test_seeded_phase3_11.py -q` passed after authoring the two seeds and their pinning test. The required `uv run pytest -q` then failed in `tests/test_seeded_phase3_10.py`, which is outside this ticket's Scope fence: it requires an obsolete activation fence and Context and cannot render the newly authored activation's existing predecessor Context sizes. It also failed in unrelated `tests/test_seeded_phase3_02.py` because `rework-stage` renders at 121584 characters above the 120000 limit. The scope fence permits neither test, so the required verification cannot be made green as written.

## Second problems filed
`tests/test_seeded_phase3_02.py` has a pre-existing `rework-stage` max-effort render-headroom failure.

## Resolved engine/model
OpenAI Codex (GPT-5)

## Predicted vs actual
Expected 75m; stopped during full-suite verification after approximately 15m.
