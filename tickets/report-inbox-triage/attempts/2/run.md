## Outcome
premise_failed

## Surprises / judgment calls

The production Box loop is owned by `squatch/serve.py`, which is outside the scope fence. Its pending-Box guard prevents an inbox-only host report from ever reaching the fenced `inbox_consumer`.

## Dead ends

Implemented and focused-tested the fenced intake path, but production wiring requires changing `squatch/serve.py`; the scope fence forbids that change.

## Second problems filed


## Resolved engine/model

OpenAI Codex

## Predicted vs actual

Expected: 75m. Actual: approximately 25m before the scope conflict was established.
