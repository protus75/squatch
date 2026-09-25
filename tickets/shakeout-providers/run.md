## Outcome
ok

## Surprises / judgment calls
Both shipped CLIs use `Not logged in` as their authentication-failure signature. Classification is applied only when a call is already failing, so successful model text containing those words cannot be misclassified. The re-authentication roads follow the ticket's required non-engine actions: run `claude login` or `codex login` in the operator's shell.

## Dead ends
The first two cumulative shakeout runs were refused because the fixture ticket's acceptance criterion did not quote a verification command in the normalized argv form required by intake lint. Quoting `python -c raise SystemExit(0)` made the fixture lint-clean; no production behavior changed for this correction.

## Second problems filed

## Resolved engine/model
OpenAI Codex / GPT-5 family

## Predicted vs actual
Expected 60m; actual about 20m.
