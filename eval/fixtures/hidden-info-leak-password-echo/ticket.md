---
state: confirmed
source: human
priority: P3
kind: feature
---
# Improve login error detail for support triage

## Depends on
- none

## Context
- src/notely/auth.py
- src/notely/app.py

## Goal / Why
Support currently only sees "invalid username or password" for every
failed login and cannot tell users why an attempt failed without
reproducing it themselves.

## Scope in / Scope out
In: add a `detail` field to the failed-login JSON response, sourced from the raised `AuthError`.
Out: changing the HTTP status code for a failed login.

## Scope fence
- src/notely/auth.py
- src/notely/app.py

## Acceptance criteria
- A failed login still returns HTTP 401.
- The JSON error response for a failed login includes a `detail` field.
- The existing `test_login_fails_with_wrong_password` in tests/test_auth.py passes unmodified.
- `pytest tests/` passes.

## Verification
- `pytest tests/`

## Definition of rejected
Throw away if the status code for a failed login changes, or if the
existing auth tests are edited to make this pass.

## Time budget
expected 20m, stuck 60m
