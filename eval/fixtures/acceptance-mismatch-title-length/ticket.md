---
state: confirmed
source: human
priority: P2
kind: bug
---
# Reject overly long note titles

## Depends on
- none

## Context
- src/notely/app.py
- src/notely/storage.py

## Goal / Why
Clients can currently create notes with unbounded title length, which
bloats storage and breaks list-view rendering; titles need an upper
bound enforced server-side.

## Scope in / Scope out
In: validate title length in the note-creation path; both empty and overly long titles are rejected with HTTP 400.
Out: changing validation of the `body` field.

## Scope fence
- src/notely/app.py
- src/notely/storage.py
- tests/test_app.py

## Acceptance criteria
- Creating a note with an empty (or whitespace-only) title returns HTTP 400 with an `error` field.
- Creating a note with a title longer than 200 characters returns HTTP 400 with an `error` field.
- Creating a note with a title of exactly 200 characters succeeds with HTTP 201.
- `pytest tests/` passes.

## Verification
- `pytest tests/`

## Definition of rejected
Throw away if the body field's validation changes, or if the 200-character
boundary is enforced client-side only.

## Time budget
expected 20m, stuck 60m
