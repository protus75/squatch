---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: high
agent_effort: high
---
## Depends on
- phase3-continue-19

## Context
- squatch/artifacts.py
- squatch/stages.py

## Plan contract
- section 20

## Goal
Define and register the daemon soak report.

## Why
The closed report must enter the ordinary lane before a soak can produce it.

## Scope in
Add `eval/daemon_soak.py` and `tests/test_daemon_soak.py`. Define the closed daemon-soak report schema in `squatch/artifacts.py` and register it in the ordinary lane's `KNOWN_ARTIFACTS` in `squatch/stages.py`. The machinery writes only through the ordinary lane and does not self-attest the committed report. The complete existing-fence and predecessor-test closure Context is `squatch/artifacts.py` and `squatch/stages.py`; no predecessor test requires migration.

## Scope out
Do not run the soak, self-attest a report, or change production code outside the report schema and ordinary-lane registration.

## Scope fence
- eval/daemon_soak.py
- tests/test_daemon_soak.py
- squatch/artifacts.py
- squatch/stages.py

## Acceptance criteria
- `tests/test_daemon_soak.py` proves the closed report schema is registered in `KNOWN_ARTIFACTS` for ordinary-lane validation.
- `tests/test_daemon_soak.py` proves daemon-soak machinery writes through the ordinary lane without self-attesting the committed report.

## Verification
```
uv run pytest tests/test_daemon_soak.py -q
uv run pytest -q
```

## Definition of rejected
Reject an open report schema, unregistered report, direct report self-attestation, or a raw outbox write.

## Time budget
- expected: 75m
- stuck: 150m
