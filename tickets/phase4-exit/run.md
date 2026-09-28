## Outcome
premise_failed

## Surprises / judgment calls
The regenerated ticket calls `tests/test_status.py` an existing activation
path, but that path is absent from the branch and has never been tracked in its
reachable history.

## Dead ends
Both the ticket and section 20 require `retro-box-activation` to fence existing
`tests/test_status.py` and treat it as a measured on-demand exception. The base
tree has `squatch/status.py` but no `tests/test_status.py`; `git ls-files` and
the path history are empty. Creating that required predecessor test would edit
`tests/test_status.py`, outside this ticket's scope fence. Authoring the child
ticket as though the path existed would instead violate its required Context
partition and existing-path contract. Per the scope-fence rule, this is an
authoring defect, so no outputs or verification commands were attempted.

## Second problems filed

## Resolved engine/model
OpenAI Codex / GPT-5 family

## Predicted vs actual
Expected 75m; actual approximately 7m before the blocking premise was proven.
