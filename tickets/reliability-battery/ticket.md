---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- provider-cooldown-failover

## Context
- squatch/artifacts.py
- squatch/stages.py

## Plan contract
- section 20

## Goal
Build the reliability fault-injection battery and its closed ordinary-lane report.

## Why
Phase 4 needs committed, schema-validated reliability evidence before its separate
no-code run can produce the report consumed by the terminal exit.

## Scope in
Add `eval/reliability_battery.py` and `tests/test_reliability_battery.py`. Define
the closed reliability-battery report schema in `squatch/artifacts.py` and register
it in the ordinary lane's `KNOWN_ARTIFACTS` in `squatch/stages.py`. The battery owns
the deterministic fault injection: it drives the merged provider cooldown/failover
boundary through classified quota exhaustion, all-candidates-cooling recovery, and
unclassified failure preservation, derives each report member from that execution
evidence, and returns the closed report only to the canonical ordinary-lane writer.
Use injected clock and process seams; do not write a report directly or self-attest
committed output. Preserve the existing artifact and stage contracts while adding
this independently provable reliability boundary.

## Scope out
Do not run the battery for a ticket-plane report, alter provider behavior, add an
independent writer or schema, implement `reliability-run`, or author Phase 4 exit.

## Scope fence
- eval/reliability_battery.py
- tests/test_reliability_battery.py
- squatch/artifacts.py
- squatch/stages.py

## Acceptance criteria
- `tests/test_reliability_battery.py` proves a closed reliability-battery report schema is registered in `KNOWN_ARTIFACTS` for ordinary-lane validation.
- `tests/test_reliability_battery.py` proves deterministic injected quota, all-candidates-cooling recovery, and unclassified-failure cases derive their report members from merged boundary evidence using injected seams.
- `tests/test_reliability_battery.py` proves the battery returns its report only to the canonical ordinary-lane writer and neither directly writes nor self-attests a committed report.

## Verification
```
uv run pytest tests/test_reliability_battery.py -q
uv run pytest -q
```

## Definition of rejected
Reject an open or unregistered report schema, direct or self-attesting report
write, uninjected fault evidence, provider behavior implementation, or a
`reliability-run` implementation in this boundary.

## Time budget
- expected: 75m
- stuck: 150m
