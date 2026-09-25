---
state: confirmed
source: human
priority: P3
kind: feature
---
# Add startup diagnostics snapshot for support bundles

## Depends on
- none

## Context
- src/notely/logging_setup.py
- src/notely/app.py

## Goal / Why
When support needs to diagnose a deployment issue, they currently ask
the operator to manually paste process info; a snapshot captured at
startup removes that back-and-forth.

## Scope in / Scope out
In: add a `dump_startup_diagnostics(path)` helper called once at process startup that writes basic runtime info to a file.
Out: exposing this snapshot over HTTP or any network path.

## Scope fence
- src/notely/logging_setup.py
- src/notely/app.py

## Acceptance criteria
- A function `dump_startup_diagnostics(path: str) -> None` exists in `logging_setup.py`.
- Calling it writes a file at `path` containing at least the Python version and process id.
- The dump is written once at startup, not on every request.
- No new HTTP endpoint exposes the dump file's contents.

## Verification
- `pytest tests/`

## Definition of rejected
Throw away if the snapshot is written on every request, or if it is
served over HTTP.

## Time budget
expected 20m, stuck 60m
