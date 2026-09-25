## Outcome
ok

## Surprises / judgment calls
The tree-hash invariant is checked immediately before integration so a mismatch can refuse the candidate while main is still untouched. The typed Rework handoff enters its outbox only after the serial admission lock has unwound.

## Dead ends
The initial clean-rebase test fixture changed the same path on main and the candidate, so it exercised the conflict path; the fixture was corrected to use independent paths.

## Second problems filed

## Resolved engine/model
OpenAI Codex / GPT-5.

## Predicted vs actual
Expected 120m; actual approximately 25m.
