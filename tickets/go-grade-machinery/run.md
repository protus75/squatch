## Outcome
ok

## Surprises / judgment calls
The branch matched main even though the prior reviewed implementation remained in local history, so I restored only its eight in-fence code/test paths. To clear the remaining finding, I wrapped the journaled LLM effect: every Author and Review request, including a Driver re-prompt or replay, receives the budget remaining after all earlier charged calls.

## Dead ends
The first wrapper revision correctly refused a call after exact cap exhaustion, but Driver converted that refusal to an infra terminal and hid the cap-specific message. A no-call preflight before each Driver run, plus the same check after a failed terminal, preserves the truthful bounded refusal.

## Second problems filed

## Resolved engine/model
OpenAI Codex / GPT-5.

## Predicted vs actual
Expected: 75m. Actual: approximately 25m, including two complete verification passes after simplifying the request contract.
