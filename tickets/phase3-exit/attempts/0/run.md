## Outcome
premise_failed

## Surprises / judgment calls
The ticket-local verification passed, but the required full suite exposed five pre-existing failures in older Phase 3 seed tests. The committed diff contains only the two new in-fence tests; the three Phase 4 ticket-plane outputs remain uncommitted as required.

## Dead ends
`uv run pytest -q` finished with 5 failures and 1224 passes. Four older authoring-headroom fixtures now exceed 120000 characters because the current section 20 render has grown, and `tests/test_seeded_phase3_22.py` expects the pre-existing `phase3-continue-23` Context to omit `squatch/artifacts.py` although that ticket includes it. Making the command green would require edits outside this ticket's fence or would contradict the current phase3-exit Context contract.

## Second problems filed
- Pre-existing red: `tests/test_seeded_phase3_01.py::test_every_seed_render_fits_requisition_headroom_with_pinned_context` renders `phase3-continue-02` at 122744 characters over the 120000 limit.
- Pre-existing red: `tests/test_seeded_phase3_08.py::test_successor_is_shrinking_and_synthetic_renders_fit_headroom` renders `dispatch-pause-boundary` at 122187 characters over the 120000 limit.
- Pre-existing red: `tests/test_seeded_phase3_10.py::test_max_effort_renders_fit_with_pinned_authoring_material` renders `phase3-continue-11` at 121254 characters over the 120000 limit.
- Pre-existing red: `tests/test_seeded_phase3_20.py::test_authoring_sizes_and_max_effort_headroom` renders `serve-activation` at 120135 characters over the 120000 limit.
- Pre-existing red: `tests/test_seeded_phase3_22.py::test_context_partitions_predecessor_closure_and_new_path_owners` omits `squatch/artifacts.py` from its expected pre-existing `phase3-continue-23` Context.

## Resolved engine/model
codex/GPT-5

## Predicted vs actual
75m expected / about 25m actual
