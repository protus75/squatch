## Outcome
premise_failed

## Surprises / judgment calls
The ticket-local verification is green, and the regenerated Phase 4 fences resolve the prior requisition findings. The required full suite is not green on the untouched base inputs.

## Dead ends
`uv run pytest -q` fails in `tests/test_seeded_phase3_23.py::test_phase4_registry_core_edges_owners_and_ordered_suffix` because the test searches `SQUATCH_PLAN.md` for the removed ``phase3-continue-23` fences` sentinel. `SQUATCH_PLAN.md`, that test, and `tickets/phase3-continue-23/ticket.md` are byte-identical to HEAD; all are outside this ticket's scope fence, so the failure cannot be repaired here.

## Second problems filed
- Pre-existing red: `tests/test_seeded_phase3_23.py::test_phase4_registry_core_edges_owners_and_ordered_suffix` raises `ValueError` while locating the removed plan sentinel. The isolated test fails with the owning inputs unchanged from HEAD.

## Resolved engine/model
codex/GPT-5

## Predicted vs actual
75m expected / about 15m actual
