## Outcome
ok

## Surprises / judgment calls
The fault callbacks are injected on the real production pipeline queue so the serve, control, worker, rework, triage, and pipeline objects remain production-composed without launching host or model work. Each fault is durably filed in its member-local Box before its report disposition is derived.

## Dead ends
An initial graph used a minimally constructed Pipeline object; it was replaced with `compose_pipeline` and the real Rework and Triage compositions before commit.

## Second problems filed

## Resolved engine/model
OpenAI / GPT-5 Codex

## Predicted vs actual
75m expected / about 35m actual
