## Outcome
premise_failed

## Surprises / judgment calls
The section-20 Phase 6 row-2 contract makes `docs/host-contract.md` the sole
Context for `fixture-host-scaffold`, although `host-contract-doc` creates that
path in the same admission. The contract also says sibling-new paths are never
Context, so no valid row-2 seed can pin both requirements.

## Dead ends
The contradiction is in the plan/ticket contract, outside this ticket's scope
fence. Repairing it would require changing `SQUATCH_PLAN.md`, which this ticket
forbids.

## Second problems filed

- `exit-receipt-machinery` also names directory `hosts/fixture/` as Context;
  the seeded-test Context convention embeds and sizes individual files, so the
  exact directory partition cannot be rendered as an ordinary Context entry.

## Resolved engine/model
OpenAI Codex; serving model identity unavailable.

## Predicted vs actual
Expected 75m; actual about 5m to establish the contract contradiction.
