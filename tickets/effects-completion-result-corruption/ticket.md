---
kind: bug
priority: P3
agent_tier: medium
agent_effort: medium
source: box:suggestion
state: draft
---

## Depends on
- none

## Context
- squatch/effects.py
- squatch/journal.py
- tests/test_effects.py

## Goal
`Effects(...)` in `squatch/effects.py` raises `JournalCorruption` naming the event's key when it rebuilds the completed-effect map from the journal and finds an `effect_completion` event whose body has no `result` field. It no longer raises a bare `KeyError`.

## Why
`squatch/effects.py:46` reads `event.body["result"]` directly, so a malformed completion event stops replay with a generic `KeyError` instead of the journal's own corruption signal -- the class that tells a caller what went wrong and how to fix it. The journal has no write-seam body validation yet, so a fix that waits for that deliverable depends on unbuilt work; this narrow read-side check instead follows the existing convention that journal shape violations surface as `JournalCorruption`, the same convention the open `journal-event-type-corruption` ticket applies to the envelope `type` field. It does not replace later write-seam validation.

## Scope in
- The `effect_completion` body read in `Effects(...)`'s replay path in `squatch/effects.py`.
- A regression test in `tests/test_effects.py` covering the missing-`result` case.

## Scope out
- Write-seam body validation for any event type (a separate, later deliverable).
- Any other body field or event type's read path, including `journal-event-type-corruption`'s envelope `type` fix.

## Scope fence
- squatch/effects.py
- tests/test_effects.py

## Acceptance criteria
- Replaying an `effect_completion` event whose body has no `result` field raises `JournalCorruption` naming the event's key, checked by `tests/test_effects.py`.
- Replaying that same event no longer raises `KeyError`, checked by `tests/test_effects.py`.

## Verification
```
pytest tests/test_effects.py -q
```

## Regression
```
pytest tests/test_effects.py -k missing_result -q
```
- carries: tests/test_effects.py

## Definition of rejected
Stop and throw the branch away if fixing this requires touching journal write-seam validation, the event schema, or any body field other than `result` on `effect_completion` -- that scope belongs to the later write-seam validation deliverable, not this ticket.

## Time budget
- expected: 20m
- stuck: 45m
