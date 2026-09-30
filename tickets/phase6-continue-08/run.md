## Outcome

premise_failed

## Surprises / judgment calls

Section 20's repaired terminal contract supplies the baseline-signal identity,
enum mapping, digest, and writer provenance, so the authored seed records those
closed inputs directly.

## Dead ends

The required full suite fails outside this ticket's scope fence in
`tests/test_seeded_phase6_02.py::test_every_emitted_ticket_renders_with_real_context_at_max_effort`:
the unchanged `phase6-continue-03` render is 120651 characters against a
120000-character limit. Its ticket, seeded test, and the plan surface are not
permitted edits for this ticket.

## Second problems filed

The Phase 6 row-2 render-bound regression above remains for its owner; no
adjacent path was changed here.

## Resolved engine/model

Unknown.

## Predicted vs actual

Expected 75m; actual approximately 12m.
