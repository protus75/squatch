## Outcome
premise_failed

## Surprises / judgment calls
The prior attempt's proposed 12,000-character-per-file model does not match the
base Implement measurement in `RequisitionReview._measure`, which renders full
Context files through `Stages.render_implement`.

## Dead ends
The required five-file Context for `retro-box-activation` plus section 20 and
the Implement prompt consumes 119,696 characters before ticket text. A
deliberately minimal lint-valid 539-character ticket renders to 120,263
characters, already above the 120,000-character requisition headroom; the real
required fence and behavioral contract can only be larger. Resolving this
requires changing the exact Context partition or shrinking plan/spec inputs,
which the scope fence forbids.

## Second problems filed

## Resolved engine/model
OpenAI Codex / GPT-5

## Predicted vs actual
Expected 75m; actual approximately 20m before the authoring contradiction was
proved.
