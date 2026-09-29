## Outcome
ok

## Surprises / judgment calls
The prior implementation was recoverable from its orphaned commit. Its release path was replaced with the queue's public admission entry, and failed releases now reuse Runner's ordinary harvest, diagnosis, terminal, and worktree-retirement path. The focused test composes through the already-inventoried helper in `tests/test_merge.py`, with no dynamic callee-name construction.

## Dead ends
The first focused run after factoring Runner's terminal handler exposed that the extracted method still referenced dispatch-local tier variables; it now reads the effective tier and effort from the already-replaced Ticket. The release-failure assertion initially compared the main SHA, but ordinary harvest lifting correctly adds a ticket-plane commit, so the proof now checks ancestry and absence of candidate code instead.

## Second problems filed

## Resolved engine/model
OpenAI / GPT-5

## Predicted vs actual
Expected 75m; actual approximately 30m.
