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
- squatch/drain.py
- tests/test_drain.py

## Goal
Each `squatch drain` report names every committed, unmerged, non-rejected ticket whose `state` is `draft` and that is not pending intake, giving `squatch confirm <stem>` as the release verb. `Drain._scan` records these stems on the returned `Plane` instead of silently skipping them, and `Drain._tail` prints one line per stem naming the verb. Confirmed tickets are scanned, dispatched, and reported exactly as before, and a draft ticket is still never dispatched.

## Why
Section 18 of SQUATCH_PLAN.md requires the drain report to list draft tickets awaiting `confirm` because box-triage-authored drafts can exist mid-build. `Drain._scan`'s `ticket.state != "confirmed"` branch (squatch/drain.py:317-318) currently `continue`s with no trace, so the operator gets no prompt to release a draft stem. The release verb `squatch confirm` already ships with the reject-verbs machinery, so this only adds a report line pointing at an existing verb.

## Scope in
- `Drain._scan` in squatch/drain.py: record each on-disk, committed, non-pending, non-merged, non-rejected stem whose lint-clean ticket has `state: draft` (instead of discarding it at the `ticket.state != "confirmed"` check).
- `Plane` in squatch/drain.py: carry the recorded draft stems through to `_tail`.
- `Drain._tail` in squatch/drain.py: print one report line per recorded draft stem naming the stem and `squatch confirm <stem>`.
- Tests in tests/test_drain.py covering the new report line and that a draft stem is never dispatched.

## Scope out
- The `confirm` verb's own behavior and the draft->confirmed state machine (already shipped).
- Any change to which stems are eligible for dispatch.
- The held-admissions report line (`facts.held_admissions`) and the reject-queue report line, both already correct.

## Scope fence
- squatch/drain.py
- tests/test_drain.py

## Acceptance criteria
- `Drain._scan` records every committed, lint-clean, unmerged, non-rejected ticket whose `state` is `draft` and whose stem is not pending intake, checked by `tests/test_drain.py`.
- `Drain._tail` prints one line per recorded draft stem naming the stem and the `squatch confirm <stem>` verb, checked by `tests/test_drain.py`.
- A stem recorded as an awaiting-confirm draft is never present in the dispatched set during the same drain run, checked by `tests/test_drain.py`.
- A committed ticket whose `state` is `confirmed` is scanned, dispatched, and reported with no change in behavior, checked by `pytest tests/test_drain.py -q`.

## Verification
```
pytest tests/test_drain.py -q
pytest -q
```

## Regression
```
pytest tests/test_drain.py -k draft_await_confirm -q
```
- carries: tests/test_drain.py

## Definition of rejected
Stop and file an RMA if recording draft stems on `Plane` requires widening dispatch eligibility to drafts, or if an existing `Plane` consumer outside `_tail` would start treating a draft stem as ready.

## Time budget
- expected: 30m
- stuck: 60m
