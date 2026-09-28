## Outcome

premise_failed

## Surprises / judgment calls

The ticket and its seed test use section 20's corrected ownership contract, including
the composition and live-Timers seams. The earlier Phase 4 seed test still asserts
the superseded smaller contract, but it is outside this ticket's scope fence.

## Dead ends

`uv run pytest tests/test_seeded_phase4_02.py -q` passed (4 passed). The required
`uv run pytest -q` failed outside the fence: two Phase 3 authoring-time render
fixtures exceed headroom (121027 and 120470 versus 120000), and
`tests/test_seeded_phase4_01.py` asserts the obsolete provider hook list. This ticket
may not edit any of those predecessor tests.

## Second problems filed

Pre-existing full-suite failures in `tests/test_seeded_phase3_01.py`,
`tests/test_seeded_phase3_08.py`, and `tests/test_seeded_phase4_01.py`.

## Resolved engine/model

OpenAI Codex, model unknown.

## Predicted vs actual

Expected 75m; actual approximately 12m.
