## Outcome

ok

## Surprises / judgment calls

The active reservation is released by awaiting the admission handle, rather than by the work task's done callback, so a completed but unobserved outcome still refuses another offer. The local AST closure scan from `squatch/__main__.py` found `squatch.daemon` unreachable; its fixture covers all three absolute import forms and an injected `import squatch.daemon` makes the fixture-only assertion fail.

## Dead ends

The prior done-callback release design was discarded because it relinquished the slot before the observer awaited the outcome.

## Second problems filed


## Resolved engine/model

OpenAI Codex / GPT-5

## Predicted vs actual

Expected 75m; actual about 25m.
