---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: high
agent_effort: high
---
## Depends on
- rework-stage

## Context
- squatch/providers.py
- squatch/config.py
- tests/test_providers.py

## Plan contract
- section 20

## Goal
Build the dormant threshold runtime for flat-subscription limits, provider concurrency, classified and unclassified CLI failures, and the circuit breaker.

## Why
Threshold decisions need one tested runtime boundary before daemon dispatch activates them, and provider failure classification may invalidate predecessor assertions in the existing provider test.

## Scope in
Add `squatch/thresh.py` as the owner of threshold state and decisions, with provider and config hooks for flat subscriptions, provider concurrency, CLI classified and unclassified failures, and breaker behavior. Add direct construction tests in `tests/test_thresh.py`; keep the construction dormant.

```yaml
ownership:
  thresh-runtime:
    owns:
      - squatch/thresh.py
      - tests/test_thresh.py
    hooks:
      - squatch/providers.py
      - squatch/config.py
      - tests/test_providers.py
```

## Scope out
Do not activate threshold decisions in daemon dispatch, add dispatch admission, or implement any later Phase 3 admission. Do not change provider behavior beyond the threshold-runtime hooks and their fenced predecessor assertions.

## Scope fence
- squatch/thresh.py
- squatch/providers.py
- squatch/config.py
- tests/test_thresh.py
- tests/test_providers.py

## Acceptance criteria
- `tests/test_thresh.py` proves flat-subscription and provider-concurrency thresholds make deterministic allow or hold decisions through the new dormant runtime.
- `tests/test_thresh.py` proves classified and unclassified CLI failures update breaker state distinctly and that the configured breaker trips and cools down at its exact boundaries.
- `tests/test_providers.py` proves the provider layer exposes the failure facts consumed by threshold runtime without changing unrelated routing, key-scoping, grant, redaction, usage, or cost behavior.
- `uv run pytest tests/test_thresh.py tests/test_providers.py -q` exits 0.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_thresh.py tests/test_providers.py -q
uv run pytest -q
```

## Definition of rejected
Stop if threshold behavior requires daemon activation, if provider failure facts cannot be exposed without contradicting behavior outside the fenced predecessor test, or if a required path lies outside this fence.

## Time budget
- expected: 120m
- stuck: 180m
