## Outcome

premise_failed

## Surprises / judgment calls

The continuation's Context contains the prior seeded test, whose source text itself mentions section 19; the render proof therefore pins the section-20-only ticket citation rather than searching the complete rendered prompt for that incidental Context text. The full suite has an unrelated plan-sentinel failure in `tests/test_seeded_phase3_23.py`.

## Dead ends

The initial render proof searched the whole rendered prompt for the section-19 heading and failed because that literal occurs in the required Context test. The check was narrowed to the authoritative ticket citation and render bound. `uv run pytest -q` fails in unchanged `tests/test_seeded_phase3_23.py`: after its Phase 4 registry start marker, `SQUATCH_PLAN.md` has no later `` `phase3-continue-23` fences`` delimiter. This ticket's fence forbids changing either path.

## Second problems filed

`tests/test_seeded_phase3_23.py` cannot delimit the Phase 4 registry because its expected later plan sentinel is absent from the unchanged base plan.

## Resolved engine/model

OpenAI / GPT-5.

## Predicted vs actual

Expected 75m; actual about 20m.
