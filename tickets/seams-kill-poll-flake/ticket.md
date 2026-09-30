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
- tests/test_seams.py

## Goal
In `tests/test_seams.py`, `test_timeout_kills_the_whole_group` and `test_cancellation_routes_through_the_same_kill` no longer sleep a fixed 0.2 seconds and check once whether the grandchild process is gone. Both call one shared polling helper that retries `os.kill(grandchild, 0)` at a short interval until it raises `ProcessLookupError`, bounded by a few-second deadline; the test fails only when the deadline expires with the grandchild still reachable. Production code is unchanged.

## Why
Both tests read the grandchild's pid from a marker file and assert it is gone 0.2 seconds after the group kill reaches it. The kill does reach the grandchild, but the orphaned grandchild still answers `kill(pid, 0)` as a zombie until init or a subreaper reaps it, and reaping can take longer than 0.2 seconds on a loaded host or under WSL/container init. The fixed sleep then fails the test even though the whole-group kill worked correctly, costing retry and infra budget and risking flake quarantine for a correct kill path. A bounded poll keeps the assertion strict -- a grandchild that survives past the deadline still fails the test -- while removing the timing race.

## Scope in
The `asyncio.sleep(0.2)` followed by a single `os.kill` check in `test_timeout_kills_the_whole_group` and in `test_cancellation_routes_through_the_same_kill`, replaced by one shared polling helper defined in `tests/test_seams.py` and called from both tests.

## Scope out
Any production code in `squatch/seams.py` or elsewhere, any other test in `tests/test_seams.py`, and the timeout values used to spawn or kill the subprocess groups under test.

## Scope fence
- tests/test_seams.py

## Acceptance criteria
- `test_timeout_kills_the_whole_group` no longer calls `asyncio.sleep(0.2)` before its `os.kill` check; it calls a shared polling helper that retries `os.kill(grandchild, 0)` until `ProcessLookupError` or a bounded deadline elapses, checked by `pytest tests/test_seams.py::test_timeout_kills_the_whole_group -q`.
- `test_cancellation_routes_through_the_same_kill` no longer calls `asyncio.sleep(0.2)` before its `os.kill` check; it calls the same shared polling helper, checked by `pytest tests/test_seams.py::test_cancellation_routes_through_the_same_kill -q`.
- Both tests call one shared polling helper defined once in `tests/test_seams.py`, checked by `pytest tests/test_seams.py -q`.

## Verification
```
pytest tests/test_seams.py::test_timeout_kills_the_whole_group -q
pytest tests/test_seams.py::test_cancellation_routes_through_the_same_kill -q
pytest tests/test_seams.py -q
```

## Regression
```
pytest tests/test_seams.py -k "test_timeout_kills_the_whole_group or test_cancellation_routes_through_the_same_kill" -q
```
- carries: tests/test_seams.py

## Definition of rejected
Stop and throw the branch away if fixing this requires touching `squatch/seams.py` or any production kill path -- the defect is in the tests' timing assertions, not the kill behavior itself.

## Time budget
- expected: 20m
- stuck: 45m
