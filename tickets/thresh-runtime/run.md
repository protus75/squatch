## Outcome

ok

## Surprises / judgment calls

The existing config already carried the concurrency, quota-window, and breaker hooks. Quota exhaustion therefore received its own per-provider cooldown rather than entering the circuit breaker; outage and unclassified failures feed the breaker, while auth, rate-limit, and model failures remain distinct for later admission policy. Known CLI failure signatures are adapter-owned allowlists, and unmatched failures remain explicitly unclassified.

## Dead ends

None.

## Second problems filed

None.

## Resolved engine/model

OpenAI / GPT-5 (Codex)

## Predicted vs actual

Expected: 120m. Actual: approximately 15m.
