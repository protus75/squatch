## Outcome
premise_failed

## Surprises / judgment calls
The required new `specs/author.md` makes the eval harness correctly report Author spec version `1.0`, while its existing test still requires `None`.

## Dead ends
`uv run pytest -q` reached 727 passing tests and failed only `tests/test_eval_harness.py::test_run_scores_every_fixture_and_journals_the_no_go_signal`. Fixing that stale expectation requires editing `tests/test_eval_harness.py`, which the Scope fence forbids.

## Second problems filed

## Resolved engine/model
OpenAI Codex / GPT-5

## Predicted vs actual
Expected 90m; actual about 25m before the scope-fence blocker was proven.
