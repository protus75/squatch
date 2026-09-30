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
- squatch/lockfile.py
- tests/test_lockfile.py

## Goal
`tests/test_lockfile.py` gains a release test that acquires a `Lockfile`, records its open file descriptor, calls `release()`, and asserts that `os.fstat` on that recorded descriptor raises `OSError`. Production code in `squatch/lockfile.py` is unchanged.

## Why
`Lockfile.release` (squatch/lockfile.py:86-91) calls `fcntl.flock(self._fd, fcntl.LOCK_UN)` and then `os.close(self._fd)`. The existing release tests (`test_release_then_reacquire`, `test_release_frees_the_lock_for_another_process`, `test_release_when_not_held_is_an_error`, `test_release_keeps_the_last_record_for_diagnostics` in tests/test_lockfile.py) check only that the lock can be re-taken, in this process and in a child, and that the holder record survives -- `LOCK_UN` alone frees the flock, so every one of them still passes if `os.close(self._fd)` is dropped from `release`. Without a test pinning the close, the daemon would leak one descriptor on every lock handoff and nothing would catch it. The open `lockfile-record-write-failure-leak` ticket covers the descriptor on acquire's failure path only, not this release path, so the gap is unowned. The fix is one test; no new machinery is needed.

## Scope in
- One new release test in `tests/test_lockfile.py` that asserts the released descriptor is closed.

## Scope out
- Any change to `squatch/lockfile.py` or `Lockfile.release`'s behavior.
- The acquire-path descriptor leak covered by `lockfile-record-write-failure-leak`.
- Any other release test's assertions or structure.

## Scope fence
- tests/test_lockfile.py

## Acceptance criteria
- A release test acquires a `Lockfile`, records `lock._fd`, calls `lock.release()`, and asserts `os.fstat` on the recorded fd raises `OSError`, checked by `pytest tests/test_lockfile.py -q`.
- The new test fails when `os.close(self._fd)` is removed from `Lockfile.release`, checked by re-running `pytest tests/test_lockfile.py -q` against that local edit before it is discarded.

## Verification
```
pytest tests/test_lockfile.py -q
```

## Definition of rejected
Stop and throw the branch away if pinning the closed descriptor requires touching `squatch/lockfile.py`, changing any other test's assertions, or a platform-specific `os.fstat`/`os.close` behavior that makes the new test flaky -- this ticket is test-only and narrow.

## Time budget
- expected: 15m
- stuck: 30m
