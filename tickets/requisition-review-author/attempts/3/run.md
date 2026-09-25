## Outcome
ok

## Surprises / judgment calls
The untouched base suite was green at 750 tests. The corrected ticket and plan explicitly allow the minimal driver terminal-findings hook. I preserved the driver's one `run_gates` call so every gate still runs, and allowed reserved stems through artifact parsing so `ticket_schema` owns their rejection while the review resolver skips the paid review.

## Dead ends
The prior implementation copied only part of ticket-schema admission into the review resolver. This attempt added the reserved-stem predicate and a focused regression before retaining that implementation.

## Second problems filed

## Resolved engine/model
OpenAI / GPT-5 Codex

## Predicted vs actual
Expected 60m; actual about 30m.
