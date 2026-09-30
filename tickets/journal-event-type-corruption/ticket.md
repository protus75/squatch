---
priority: P3
kind: bug
agent_tier: medium
agent_effort: medium
source: box:suggestion
state: draft
---
## Depends on
- none

## Context
- squatch/journal.py
- tests/test_journal.py

## Plan contract
- section 6

## Goal
`_parse_event` in `squatch/journal.py` rejects an event whose `type` field is not a string with a `ValueError`, checked before the `EVENT_TYPES` membership test. `_read_segment` converts that `ValueError` into `JournalCorruption` carrying the segment path and line number, exactly as it already does for every other envelope violation. A regression test in `tests/test_journal.py` writes a segment line whose `type` is a JSON list and asserts that reading it raises `JournalCorruption`, not `TypeError`.

## Why
The envelope check at `squatch/journal.py:72` runs `obj["type"] not in EVENT_TYPES` against a frozenset. When `obj["type"]` is an unhashable JSON value (a list or object), that membership test raises `TypeError` instead of the `ValueError` every other envelope violation raises. `_read_segment` (`squatch/journal.py:212-215`) only catches `ValueError` and converts it to `JournalCorruption`, so the `TypeError` escapes unchanged: the read still fails closed, but a caller that catches `JournalCorruption` specifically to handle corruption sees the wrong exception class and loses the path/line context that conversion attaches.

## Scope in
In `_parse_event`, check that `obj["type"]` is a string before testing it against `EVENT_TYPES`, raising the same `ValueError` shape as the existing unknown-type case when it is not. Add one regression test in `tests/test_journal.py` that seeds a segment with a non-string (list) `type` and asserts `Journal.read()` raises `JournalCorruption`.

## Scope out
No change to `EVENT_TYPES`, `RESERVED_TYPES`, `Event`, `render_ts`, the other envelope field checks (`v`, `ts`, `ticket`, `key`, `body`), `_read_segment`'s existing `ValueError`-to-`JournalCorruption` conversion, or any reader/replay/roll logic.

## Scope fence
- squatch/journal.py
- tests/test_journal.py

## Acceptance criteria
- `_parse_event` raises `ValueError` (never `TypeError`) when `obj["type"]` is a non-string JSON value, checked by `python -m pytest tests/test_journal.py -k test_unhashable_type_on_read_is_corruption -q`.
- Reading a segment whose `type` field is a JSON list raises `JournalCorruption` carrying the segment path and line number, not `TypeError`, checked by the same test.
- `python -m pytest tests/test_journal.py -q` exits 0.
- `python -m pytest -q` exits 0.

## Verification
```
python -m pytest tests/test_journal.py -k test_unhashable_type_on_read_is_corruption -q
python -m pytest tests/test_journal.py -q
python -m pytest -q
```

## Regression
```
python -m pytest tests/test_journal.py -k test_unhashable_type_on_read_is_corruption -q
```
- carries: tests/test_journal.py

## Definition of rejected
Stop and answer premise_failed if the fix requires an unhashable-type guard anywhere in the envelope validation beyond the `type` field, a change to `EVENT_TYPES`, `RESERVED_TYPES`, or `_read_segment`'s conversion logic, or a file outside the two fenced modules, or if the new test is red on the base commit for a reason other than the reported `TypeError`.

## Time budget
- expected: 20m
- stuck: 45m
