## Outcome

premise_failed

## Surprises / judgment calls

The baseline-binding-reader contract requires `squatch/policy.py` to stop being
the binding reader and `squatch/author.py` to be its sole caller, but this
ticket fences neither `squatch/policy.py` nor `tests/test_policy.py`.

## Dead ends

On the base commit, `squatch.policy.go_binds` remains the production binding
reader and `squatch.author` imports and calls it. `tests/test_policy.py` imports
that function directly. Adding `squatch/baseline.py` within the proposed seed
would leave two production readers; removing or migrating the old reader would
require edits outside this ticket's scope fence. The plan and seed fence must
be repaired before this admission can be authored.

## Second problems filed


## Resolved engine/model

OpenAI Codex, GPT-5.

## Predicted vs actual

Expected 75m; actual about 5m before the premise failure.
