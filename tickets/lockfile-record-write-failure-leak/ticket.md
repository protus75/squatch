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
- squatch/lockfile.py
- tests/test_lockfile.py

## Goal
`Lockfile.acquire` in `squatch/lockfile.py` closes the freshly flocked descriptor and re-raises the original exception whenever building the `Holder` record, `os.ftruncate`, or `os.write` raises after a successful `flock`. `self._fd` is set only once that record write has succeeded, so `held` never reports `False` while an open, flocked descriptor is still live.

## Why
Only the `flock` call is inside the current close-on-failure guard. Building the `Holder` (the clock seam, `socket.gethostname`) and the `ftruncate`/`write` pair that follow it run unguarded, so an exception there leaves an open, flocked descriptor behind while `self._fd` stays `None` and `held` stays `False`. An flock lock belongs to the open file description, not the path, so every later `os.open` + `flock` on `squatch.lock` in that same process then hits `BlockingIOError`, and `acquire` reports it as an unidentified holder until the process exits -- even though this `Lockfile` believes it holds nothing. The daemon dies on the triggering exception anyway, so this is not a stall there, but any process that catches the exception and keeps running -- tests, one-shot verbs -- is left with a lock it can never reacquire. Widening the existing guard over the record write closes the gap with no new path.

## Scope in
- The record-write step (`Holder` construction, `ftruncate`, `write`) in `Lockfile.acquire`, closing the descriptor on any exception there the same way the `flock` step already does.
- A regression test in `tests/test_lockfile.py` using a raising clock.

## Scope out
- The `flock` acquisition guard itself (already correct).
- `release()` and `_read_holder()` (unaffected).
- Any retry or stale-descriptor reclaim machinery -- this fix prevents the leak outright, it does not work around one.

## Scope fence
- squatch/lockfile.py
- tests/test_lockfile.py

## Acceptance criteria
- A clock, `gethostname`, `ftruncate`, or `write` failure between a successful `flock` and `self._fd` being set closes the descriptor and re-raises the original exception, checked by `tests/test_lockfile.py`.
- After such a failure `held` is `False` and a subsequent `acquire` on the same `Lockfile` with a working clock succeeds instead of raising `LockHeld`, checked by `tests/test_lockfile.py`.

## Verification
```
pytest tests/test_lockfile.py -q
```

## Regression
```
pytest tests/test_lockfile.py -k after_flock_closes -q
```
- carries: tests/test_lockfile.py

## Definition of rejected
Stop and throw the branch away if fixing this requires changing the `flock` acquisition path itself, `release()`, or the on-disk record schema -- this ticket only widens the existing close-on-failure guard over the record write.

## Time budget
- expected: 20m
- stuck: 45m
