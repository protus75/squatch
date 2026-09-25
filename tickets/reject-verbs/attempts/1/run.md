## Outcome
premise_failed

## Surprises / judgment calls
The required `premise_bounce` draw changes an existing assertion in `tests/test_drain_upgrade.py`, but that path is outside this ticket's scope fence.

## Dead ends
Implemented the scoped behavior and ran the required focused checks successfully. The full suite then failed at `tests/test_drain_upgrade.py::test_a_premise_failed_stem_is_parked_without_a_draw_and_runs_again_after_its_edit_lands`, whose assertion requires no cap draw and directly contradicts the ticket's required `premise_bounce` draw. The implementation was removed because the contract forbids editing that out-of-fence test.

## Second problems filed

## Resolved engine/model
OpenAI Codex; model identity not exposed.

## Predicted vs actual
Expected 60m; actual about 20m before the scope-fence blocker was proven.
