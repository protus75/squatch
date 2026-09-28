## Outcome

premise_failed

## Surprises / judgment calls

Section 20 now makes the scorecard contract concrete, but it still gives
`status-projection` and `baseline-binding-reader` only names and partial
ownership. It neither supplies their behavioral contracts nor the direct
dependency edges that the required next seeded test must pin.

## Dead ends

The required base targeted verification could not run because
`tests/test_seeded_phase5_01.py` does not exist on the base commit. The plan
gap blocks authoring it: a section-20-only continuation would have to invent
the status projection fields and baseline reader's ABSENT/NO_GO/GO/REVOKED,
torn-tail, revocation, and registry/spec-major delivery rules. The concrete
production caller is `squatch/author.py`, not `squatch/policy.py`, which only
defines `starting_state` and `go_binds`.

## Second problems filed



## Resolved engine/model

OpenAI / GPT-5

## Predicted vs actual

Expected 75m; actual about 10m.
