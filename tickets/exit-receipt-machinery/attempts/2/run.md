## Outcome
premise_failed

## Surprises / judgment calls
The fixture's `triage` call would inherit its `review` routing row, but its scripted `codex` executable accepts only author, implement, and review surfaces. I treated the real serve-to-inbox-to-triage path as required evidence rather than fabricating a bug-loop or escape observation.

## Dead ends
The report-to-regression loop cannot be driven through real `serve`: after inbox intake it invokes the triage surface, which `hosts/fixture/bin/codex` rejects. Adding a triage route/response requires edits to `hosts/fixture/config.yaml` and `hosts/fixture/bin/codex`, both outside the scope fence.

## Second problems filed

## Resolved engine/model
OpenAI / Codex

## Predicted vs actual
Expected 75m; stopped during premise audit after approximately 8m.
