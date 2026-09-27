---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- phase3-continue-15

## Context
- squatch/journal.py
- tests/test_journal.py

## Plan contract
- section 20

## Goal
Roll the journal at its fixed Phase 3 bounds without changing replay.

## Why
The storm occurrence fold needs the complete ordered stream across immutable segments.

## Scope in
Implement the fixed 64 MiB or 24h journal-roll trigger in `squatch/journal.py` and prove it in new `tests/test_journal_roll.py`. Segments remain ordered and immutable after rolling; replay reads all segments in order with existing torn-tail rules. `tests/test_journal.py` is read-only preservation: run it unchanged; replay across rolled segments is proved in `tests/test_journal_roll.py`.

## Scope out
Do not add retention or GC, alter existing journal tests, or implement storm behavior.

## Scope fence
- tests/test_journal_roll.py
- squatch/journal.py

## Acceptance criteria
- `tests/test_journal_roll.py` proves rolling at 64 MiB or 24h creates the next ordered active segment, leaves earlier segments immutable, and preserves replay across rolled segments.
- `tests/test_journal.py` passes unchanged as read-only preservation.

## Verification
```
uv run pytest tests/test_journal_roll.py -q
uv run pytest tests/test_journal.py -q
uv run pytest -q
```

## Definition of rejected
Reject a changed preservation test, retention/GC, unordered segments, or a replay regression.

## Time budget
- expected: 75m
- stuck: 150m
