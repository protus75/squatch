## Outcome
premise_failed

## Surprises / judgment calls
The untouched branch go-grade-machinery at bf791f432226e9874928101d35bf661b458141fa contains the original Phase 1 harness, not the prior attempts' GO-grade implementation. Section 20 requires a fixed USD 5.00 cap, and the ticket explicitly rejects overflow. The missing enforceable spend boundary is an authoring/fence defect, not a reason to weaken that requirement.

## Dead ends
The strict cap cannot be implemented through the current production LLM seam within this fence. squatch/llm.py LLMRequest has no budget or token-limit field. squatch/config.py Limits has concurrency, est_cost_per_call_usd, and quota_window_minutes, but no maximum tokens, prices, or enforceable per-call upper bound. squatch/providers.py ClaudeAdapter.argv supplies no spend/token limit, and CliClient.call_resolved reads total cost only after the process returns, preferring reported cost over the estimate (lines 464-470). Thus even the first admitted call can exceed USD 5.00; checking afterward cannot undo spending. Reserving against an estimate or prior maximum cannot establish the required bound. A harness-local alternate provider/argv path would be the prohibited shim.
Paved road: author prerequisite ownership for an enforceable provider spend bound through squatch/llm.py and squatch/providers.py (and squatch/config.py if configured), with its tests, before this harness ticket. Those paths are outside this scope fence. Stopped before code edits as instructed for authoring defects. No verification commands were run, no terminal report or production signal was produced, and no commit was made.

## Second problems filed

## Resolved engine/model
OpenAI / GPT-6 (Codex), as identified by the session instructions; exact serving variant unavailable.

## Predicted vs actual
Expected: 75 minutes. Actual: approximately 5 minutes of read-only premise inspection and run-record preparation; stopped at the scope blocker.
