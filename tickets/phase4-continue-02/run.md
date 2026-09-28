## Outcome

ok

## Surprises / judgment calls

The authored ticket files were already present from the engine's prior lift, so this
attempt committed only the required test contract. The historical Phase 3 render
fixtures pin the measured section-20 sizes at their authoring commits: 8,911,
11,661, and 12,826 characters.

## Dead ends

The first historical-section substitution omitted the final newline, which joined
the synthetic section to the section-21 heading and made the resolver include the
appendix. Preserving that newline restored the intended exact historical slice.

## Second problems filed

None.

## Resolved engine/model

OpenAI Codex (exact serving model not exposed).

## Predicted vs actual

Expected 75m; actual approximately 15m in this attempt.
