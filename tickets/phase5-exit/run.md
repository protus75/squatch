## Outcome
ok

## Surprises / judgment calls
The engine had already lifted the three previously authored Phase 6 child tickets, while the two proof files remained only in the prior unmerged implementation commit. I restored those scoped proofs and bounded retrospective selection to committed first-parent history through the commit that adds the exit proof, so later Phase 6 reports cannot change the selected Phase 5 evidence.

## Dead ends
The prior proof selected the latest report at HEAD and pinned `000010`; that approach was abandoned because any later drain-produced report would invalidate it.

## Second problems filed

## Resolved engine/model
OpenAI / GPT-5 Codex

## Predicted vs actual
Expected 75m; actual approximately 15m. Focused verification passed 12 tests and the full suite passed 1,508 tests.
