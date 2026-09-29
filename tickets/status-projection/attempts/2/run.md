## Outcome
premise_failed

## Surprises / judgment calls
The branch did not contain the prior attempt's implementation, so the complete status projection was reconstructed. HEAD and retro-spec failures now use the established refusal surface.

## Dead ends
The full-suite verification cannot pass within this fence: `tests/test_seeded_phase2.py::test_context_refuses_governed_engine_prose` rejects the unchanged `tickets/spine-harvest` Context entry `tests/test_cli.py`.

## Second problems filed

- `tests/test_seeded_phase2.py::test_context_refuses_governed_engine_prose` is pre-existing and outside this ticket's fence; `git diff HEAD -- tickets` is empty.

## Resolved engine/model
OpenAI Codex / GPT-5

## Predicted vs actual
Expected: 75m. Actual: about 60m.
