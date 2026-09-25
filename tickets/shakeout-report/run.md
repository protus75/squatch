## Outcome
ok

## Surprises / judgment calls
The production composer constructs its routed CLI effect internally, so the bench composes it first and replaces only the stage and diagnosis LLMEffect references with the supplied FakeLLM-backed effect; Runner, Drain, Stages, Merge, and their shared journal remain the production object graph.

## Dead ends
The first two-ticket bench fixture reused a parent directory without `exist_ok`, causing the second scripted implementation to fail and enter diagnosis; the fixture action was corrected and the bench now also routes diagnosis through the fake effect.

## Second problems filed

## Resolved engine/model
OpenAI Codex, GPT-5

## Predicted vs actual
Expected 75m; actual approximately 45m.
