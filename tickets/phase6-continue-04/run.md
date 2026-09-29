## Outcome

premise_failed

## Surprises / judgment calls

The repaired section-20 registry now makes the authored `escape-column` fence buildable, including its Retro and CLI callers.

## Dead ends

`uv run pytest -q` fails in the unchanged `tests/test_seeded_phase6_02.py::test_every_emitted_ticket_renders_with_real_context_at_max_effort`: it renders unchanged `phase6-continue-03` against the unchanged plan at 120952 characters, above the 120000 limit. The failing test, rendered ticket, and plan are outside this ticket's fence and have no diff from HEAD, so this ticket cannot make every required verification command green.

## Second problems filed

Historical Phase 6 row-2 render-headroom guard needs a plan/test correction outside this ticket's fence.

## Resolved engine/model

OpenAI / GPT-5.

## Predicted vs actual

Expected 75m; actual about 15m.
