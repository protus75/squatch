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
- squatch/status.py
- squatch/artifacts.py
- squatch/drain.py
- tests/test_status.py

## Goal
`project` in `squatch/status.py` no longer lists a stem in `ready` when its latest `state_transition` is `to: rejected`, even while its latest intake signal still records `state: confirmed`. That stem is listed only in `stopped`, matching `squatch/drain.py`'s own eligibility check, which already excludes a latest `rejected` transition from dispatch.

## Why
The ready fold at `squatch/status.py:124` accepts any latest transition whose `to` is in `TERMINAL_RUN_STATES` (`squatch/artifacts.py:61`), and that set includes `rejected`. In the ordinary `squatch reject` path the re-intake through `Intake.commit_lane` flips the latest intake signal's `state` away from `confirmed`, which already keeps the stem out of `ready` through the `rec.state != "confirmed"` check one line above. Two kill paths skip that re-intake and leave the latest intake signal at `confirmed`: a journal-only kill of an unstampable ticket or a dirless identity, and a crash between the `rejected` transition write and the follow-up `commit_lane` call. In both cases a killed stem reads as both `stopped: rejected` and `ready`, even though the drain will never dispatch it. `status` is the operator's read-only projection; a projection that disagrees with the scheduler about whether a stem can still run sends the operator after work that cannot happen.

## Scope in
Exclude a latest `to: rejected` transition from the `ready` fold in `squatch/status.py`, while leaving every other stopped terminal (failed outcomes, `abandoned`) listed as ready exactly as it is today. Add a regression test in `tests/test_status.py` that builds a journal with a `confirmed` intake signal followed by a `state_transition` to `rejected` and no later intake signal, and asserts the stem appears in `stopped` and not in `ready`.

## Scope out
No change to the `stopped`, `blocked`, `in_flight`, or `merged` folds, to `TERMINAL_RUN_STATES` itself, to `squatch/drain.py`'s own eligibility check, or to the ordinary `squatch reject` re-intake path.

## Scope fence
- squatch/status.py
- tests/test_status.py

## Acceptance criteria
- A stem whose latest `state_transition` is `to: rejected` and whose latest intake signal is `confirmed` appears in `Status.stopped` and not in `Status.ready`, checked by a new case in `tests/test_status.py`.
- Every other stopped terminal (a failed `Outcome` or `abandoned`) is still listed in both `Status.stopped` and `Status.ready` exactly as before, checked by the existing cases in `tests/test_status.py`.
- `python -m pytest tests/test_status.py -q` exits 0.
- `python -m pytest -q` exits 0.

## Verification
```
python -m pytest tests/test_status.py -q
python -m pytest -q
```

## Regression
```
python -m pytest tests/test_status.py -q -k rejected
```
- carries: tests/test_status.py

## Definition of rejected
Stop and answer premise_failed if excluding `rejected` from the ready fold requires changing `TERMINAL_RUN_STATES`, `squatch/drain.py`'s eligibility check, or any file outside the two fenced paths, or if `tests/test_status.py` is red on the base commit before any edit.

## Time budget
- expected: 20m
- stuck: 45m
