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
- tests/test_journal_roll.py

## Plan contract
- section 6

## Goal
`Journal.__init__` names the first segment, and `Journal._roll` names every rolled segment, from the UTC-normalized clock value, so a segment filename's date always matches the UTC date carried by the `ts` of the events inside it. An aware clock in a non-UTC zone near a UTC day boundary no longer produces a segment name dated one day off from its own events.

## Why
`squatch/journal.py` builds segment names straight from the clock's own zone in two places -- the first segment in `__init__` (line 95) and the next active segment in `_roll` (line 152) -- while `render_ts` always normalizes `ts` to UTC before writing it (line 51). When the injected clock is aware but not UTC, the segment filename's date can disagree with the UTC date carried by the events it holds. The journal-roll ticket has already merged and repeats the same clock-to-name pattern at both call sites, so the fix must cover both consistently with the one pinned `ts` rendering.

## Scope in
In `squatch/journal.py`, render the segment date in both `__init__` and `_roll` from the clock value normalized to UTC (`astimezone(timezone.utc)`), matching `render_ts`'s normalization. Add one regression test in `tests/test_journal.py` for the first-segment name and one in `tests/test_journal_roll.py` for the rolled-segment name, each driven by an aware non-UTC clock positioned so its local date and UTC date differ.

## Scope out
No change to the roll trigger conditions (`_should_roll`, `_MAX_SEGMENT_AGE`, `_MAX_SEGMENT_BYTES`), to `render_ts`, to the segment name regex `_SEGMENT_NAME`, or to any reader/replay logic.

## Scope fence
- squatch/journal.py
- tests/test_journal.py
- tests/test_journal_roll.py

## Acceptance criteria
- `Journal.__init__` names the first segment using the UTC date of the injected clock value even when the clock is aware but not UTC and its local date differs from its UTC date, checked by `python -m pytest tests/test_journal.py -k test_first_segment_name_uses_utc_date_for_non_utc_aware_clock -q`.
- `Journal._roll` names a newly rolled segment using the UTC date of the clock value at roll time even when the clock is aware but not UTC, checked by `python -m pytest tests/test_journal_roll.py -k test_rolled_segment_name_uses_utc_date_for_non_utc_aware_clock -q`.
- `python -m pytest tests/test_journal.py tests/test_journal_roll.py -q` exits 0.
- `python -m pytest -q` exits 0.

## Verification
```
python -m pytest tests/test_journal.py -k test_first_segment_name_uses_utc_date_for_non_utc_aware_clock -q
python -m pytest tests/test_journal_roll.py -k test_rolled_segment_name_uses_utc_date_for_non_utc_aware_clock -q
python -m pytest tests/test_journal.py tests/test_journal_roll.py -q
python -m pytest -q
```

## Regression
```
python -m pytest tests/test_journal.py tests/test_journal_roll.py -q -k utc_date
```
- carries: tests/test_journal.py
- carries: tests/test_journal_roll.py

## Definition of rejected
Stop and answer premise_failed if the fix needs a change to the roll trigger conditions, `render_ts`, the segment name regex, or any file outside the two fenced modules and their tests, or if either new test is red on the base commit for a reason other than the reported defect.

## Time budget
- expected: 30m
- stuck: 75m
