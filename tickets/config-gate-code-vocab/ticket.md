---
kind: bug
priority: P2
agent_tier: medium
agent_effort: medium
source: box:suggestion
state: draft
---

## Depends on
- none

## Context
- squatch/config.py
- squatch/artifacts.py
- tests/test_config.py
- tests/test_daemon_config.py

## Goal
Loading a config fails with a `ConfigError` when a key of `review.gate_severity`, or a gate code in any `review.trigger_map` value list, is not a member of `GATE_CODES` (`squatch/artifacts.py`). The finding names the offending dotted config path and lists the allowed codes. A test in `tests/test_config.py` loads a config with a misspelled `gate_severity` key and checks that load is refused, and another does the same for an out-of-vocabulary `trigger_map` code. `merge.safety_checks` is unchanged: it holds host-designated codes, not engine ones.

## Why
`squatch/providers.py:271-279` already refuses a `cli` provider with no `est_cost_per_call_usd` when its adapter reports no usage, and already refuses a `routing[].surface` outside the `llm_surface` set. The remaining open concern is `review.trigger_map` and `review.gate_severity`: `squatch/config.py` types both as plain `dict[str, list[str]]` / `dict[str, Severity]` with no cross-check, and `squatch/gates.py:178` merges `{**SHIPPED_GATE_SEVERITY, **severity}`. A misspelled key is silently dropped and the gate keeps its shipped default -- fail-open against what section 15 states is a closed, engine-shipped vocabulary. `GATE_CODES` already exists, so this is a load-time membership check, no new vocabulary and no dependency on `squatch/gates.py` itself.

## Scope in
- A validator in `squatch/config.py`'s `Review` model checking every `trigger_map` value's codes and every `gate_severity` key against `GATE_CODES` (imported from `squatch/artifacts.py`), raising the same dotted-path `ConfigError` shape as every other schema refusal in this file.
- Updating the shared `VALID` fixture in `tests/test_config.py` (`trigger_map: {"squatch/": ["SCHEMA"]}`, `gate_severity: {"SCHEMA": "hard"}`) to use a real `GATE_CODES` member (e.g. `verification`) in place of `SCHEMA`, so every test that already parses `VALID` or a `variant()` of it stays green.
- Updating the `VALID` fixture in `tests/test_daemon_config.py` (`trigger_map: {"squatch/": ["TEST"]}`) to the same real gate code in place of `TEST`, so its snapshot-detachment tests keep passing.
- Two new refusal tests in `tests/test_config.py`: a `gate_severity` key outside `GATE_CODES` is refused, and a `trigger_map` value listing a code outside `GATE_CODES` is refused; each asserts the finding names the offending path.

## Scope out
- `merge.safety_checks` and `squatch/gates.py` -- host-designated codes at merge, unaffected by this change.
- `routing[].surface` / the `llm_surface` vocabulary and `providers.py` -- already enforced.
- Any change to `GATE_CODES` itself or to `squatch/gates.py`'s severity merge.

## Scope fence
- squatch/config.py
- tests/test_config.py
- tests/test_daemon_config.py

## Acceptance criteria
- `parse()` raises `ConfigError` when a `review.trigger_map` value lists a code outside `GATE_CODES`, naming the `review.trigger_map.<prefix>` path and listing the allowed codes -- checked by a new test in `tests/test_config.py`.
- `parse()` raises `ConfigError` when a `review.gate_severity` key is outside `GATE_CODES`, naming the `review.gate_severity.<code>` path and listing the allowed codes -- checked by a new test in `tests/test_config.py` that loads a config with a misspelled `gate_severity` key.
- `merge.safety_checks` accepts arbitrary string values unchanged -- checked by the existing merge tests in `tests/test_config.py` passing unmodified.
- Every existing test in `tests/test_config.py` and `tests/test_daemon_config.py` passes once their fixtures' `trigger_map`/`gate_severity` codes are real `GATE_CODES` members.

## Verification
```
pytest tests/test_config.py -q
pytest tests/test_daemon_config.py -q
```

## Regression
```
pytest tests/test_config.py -k gate_severity_key_outside_gate_codes_is_refused -q
```
- carries: tests/test_config.py

## Definition of rejected
Stop and throw the branch away if the fix requires `squatch/config.py` to import `squatch/gates.py` or any other stage/gate module -- importing `GATE_CODES` from `squatch/artifacts.py` is the sanctioned dependency, and config.py depending on gates.py would be the layering inversion this contract forbids. Also stop if it requires changing `merge.safety_checks` to validate against `GATE_CODES`, or changing `GATE_CODES` itself.

## Time budget
- expected: 30m
- stuck: 60m
