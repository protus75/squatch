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
- tests/test_config.py

## Goal
When `load` refuses a config because a provider's `auth` is not an env-var name, the `ConfigError` raised by `_auth_is_an_env_var_name` in `squatch/config.py` names the offending dotted key path and the paved road (use an env-var NAME such as `ANTHROPIC_API_KEY`), and never contains the refused value itself.

## Why
The check in `_auth_is_an_env_var_name` (`squatch/config.py:70-75`) exists because an operator may have pasted a real secret into `auth`. The section 6 redaction seam only scrubs values resolved from configured env-var NAMES; a literal typed directly into `auth` names no env var, so that seam cannot catch it. The validator's message currently appends `got {v!r}`, echoing the literal straight into the raised `ValueError`, which `_finding` passes through unchanged into the `ConfigError` the daemon's `config_supplier` re-reads on every dispatch -- so a load refusal can land the secret in stderr and the engine log, where it then persists forever (the journal/log is never scrubbed after the fact). The dotted key path (`providers[N].auth`) already tells the operator exactly where the problem is; the echoed value adds nothing they need and is the one thing that must never be captured.

## Scope in
- Drop the `; got {v!r}` tail from the `ValueError` raised in `_auth_is_an_env_var_name` (`squatch/config.py`), keeping the paved-road wording that already states the required shape and gives `ANTHROPIC_API_KEY` as an example.
- A test in `tests/test_config.py` proving a secret-shaped literal `auth` value (e.g. `sk-ant-test-literal`) is refused and never appears in `str()` of the raised `ConfigError`.

## Scope out
- The section 6 redaction seam and its env-var-name resolution path (out of scope: this literal names no env var, so that seam cannot and should not be touched here).
- Any other `ConfigError` finding's wording, `_finding`, or `_dotted` (unchanged; only this one validator's message changes).
- The existing `test_auth_must_be_an_env_var_name_never_a_literal_secret` parametrization itself (left in place; it already asserts only `"env" in str(err)`, not the absence of the literal).

## Scope fence
- squatch/config.py
- tests/test_config.py

## Acceptance criteria
- `_auth_is_an_env_var_name`'s raised message no longer contains `got {v!r}` or any other echo of the rejected value, checked by `tests/test_config.py`.
- Loading a config whose provider `auth` is a secret-shaped literal (e.g. `sk-ant-test-literal`) is refused with `ConfigError.key == "providers[0].auth"`, checked by `tests/test_config.py`.
- That literal value appears nowhere in `str()` of the raised `ConfigError`, checked by `tests/test_config.py`.

## Verification
```
pytest tests/test_config.py -q
```

## Regression
```
pytest tests/test_config.py -k auth_refusal_never_echoes -q
```
- carries: tests/test_config.py

## Definition of rejected
Stop and throw the branch away if removing the value echo requires changing `_finding`, `_dotted`, or any other validator's message, or if it breaks the existing `"env" in str(err)` assertion in `test_auth_must_be_an_env_var_name_never_a_literal_secret` -- this ticket is a one-line message trim on a single validator, not a redaction-seam or finding-format change.

## Time budget
- expected: 15m
- stuck: 30m
