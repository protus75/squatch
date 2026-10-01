---
kind: chore
priority: P3
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

## Goal
`tests/test_journal.py` gains a test proving that a complete, well-formed JSON event record written with no trailing newline to the active segment's file -- through a second file handle, while a `Journal` instance stays open -- is still treated as an uncommitted tail: `j.read()` and `read_segments()` return only the events appended before it. Production code in `squatch/journal.py` is unchanged.

## Why
`_read_segment` (squatch/journal.py:203-213) drops every byte after the active segment's last newline without inspecting it, and `_truncate_torn_tail` (squatch/journal.py:232-239) deletes those same bytes at the next startup regardless of whether they parse as JSON. The existing tail tests -- `test_torn_final_line_of_active_segment_is_skipped` and `test_read_segments_tolerates_a_torn_tail_only_in_the_active_segment` -- only ever write a tail that fails `json.loads`, and the fault-injection harness in `tests/test_fault_injection.py` always restarts through `Journal.__init__`, which truncates the tail before any read happens. So a reader change that tried `json.loads` on the tail and kept it when it parsed would pass every test today, while producing a view that a restart silently retracts afterward. One more test case, shaped like `test_torn_final_line_of_active_segment_is_skipped` but with a syntactically complete record, closes that gap without adding a new seam or harness fault point.

## Scope in
- One new test in `tests/test_journal.py` asserting that a complete-JSON, no-newline tail on the active segment is excluded by both `Journal.read()` and `read_segments()`.

## Scope out
- Any change to `squatch/journal.py` or any other production module.
- Any change to `tests/test_fault_injection.py` or its restart model.

## Scope fence
- tests/test_journal.py

## Acceptance criteria
- A test opens a `Journal`, appends two events, then writes one complete, valid JSON event record with no trailing newline to the active segment's file through a second handle, and asserts `[e.body["n"] for e in j.read()]` equals only the two committed events' `n` values, checked by `pytest tests/test_journal.py -k active_tail_valid_json`.
- The same scenario read through `read_segments()` instead of `j.read()` asserts the returned active segment's tuple holds only the two committed events, checked by `pytest tests/test_journal.py -k active_tail_valid_json`.
- `squatch/journal.py` carries no diff from its current committed content, checked by `git diff --stat squatch/journal.py` producing no output.

## Verification
```
pytest tests/test_journal.py -k active_tail_valid_json
pytest tests/test_journal.py
git diff --stat squatch/journal.py
```

## Definition of rejected
Stop and discard the branch if making the new case pass requires any change to `squatch/journal.py`: that would mean the reader already treats a complete-but-unterminated tail as committed, a production defect out of this chore's scope that belongs in its own bug ticket, not folded into this test-only change.

## Time budget
- expected: 15m
- stuck: 45m
