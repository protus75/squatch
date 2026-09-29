## Outcome

ok

## Surprises / judgment calls

- The current branch lacked the earlier implementation. Restored its scoped changes from reviewed commit fd164c4308d3fa7cf451f1768430b23ee195287a.
- The Phase 2 Context-refused set was already a pinned historical literal on the base. Added an equality assertion against that historical set; no live file sizes are read.
- A merged-then-running stem remains merged by its latest terminal transition and also appears in flight by its latest unmatched running transition, following section 20's independent folds.
- Both verification commands exited 0: targeted suite 130 passed; full suite on committed HEAD 1454 passed. Commit: 3756c4f4e20c233aa50bdad7275f5d0194c44218.

## Dead ends

The prior attempt's live-size regression test was not retained because later file growth or trimming must not alter historical admission evidence.

## Second problems filed

## Resolved engine/model

OpenAI / GPT-6 (Codex).

## Predicted vs actual

Expected: 75m. Actual: approximately 6m.
