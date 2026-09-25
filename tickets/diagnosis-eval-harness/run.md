## Outcome
ok

## Surprises / judgment calls
The prior implementation commit was available locally but absent from this re-entry branch, so I restored that scoped commit and corrected it in a second commit. I treated a budget refusal on call two as a terminal for the partly run fixture, preserving its paid first-call cost while listing only untouched fixtures as not run.

## Dead ends
The untouched base suite passed before restoration (608 tests). The prior shared ticket template was discarded because it contradicted the fixture evidence; each envelope now carries a ticket specific to the failure being diagnosed.

## Second problems filed

## Resolved engine/model
OpenAI / GPT-5

## Predicted vs actual
Expected 90m; actual about 30m. Verification passed: 14 focused tests, CLI help, and 622 full-suite tests.
