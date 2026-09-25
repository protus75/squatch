---
state: confirmed
source: human
priority: P2
kind: chore
---
# Add per-request access logging

## Depends on
- none

## Context
- src/notely/app.py
- src/notely/logging_setup.py

## Goal / Why
Ops needs one log line per request (method, path, resulting status) to
triage latency and error-rate issues without attaching a debugger.

## Scope in / Scope out
In: log one INFO line per request in `NotelyApp.__call__` using the `notely` logger.
Out: changing any response body, header, or status code.

## Scope fence
- src/notely/app.py

## Acceptance criteria
- Every request produces exactly one INFO log line naming the HTTP method and path.
- Every request's log line includes the response status code.
- No response body, header set, or status code changes as a result of this change.
- `pytest tests/` passes unchanged.

## Verification
- `pytest tests/`

## Definition of rejected
Throw away if logging is added per-route instead of centrally, or if it
changes any existing response.

## Time budget
expected 20m, stuck 60m
