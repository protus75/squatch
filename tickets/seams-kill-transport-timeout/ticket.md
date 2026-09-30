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
- squatch/seams.py
- tests/test_seams.py

## Goal
When `SubprocessExec.run` in `squatch/seams.py` times out or is cancelled, its kill path always finishes within a short fixed bound, even when a descendant has left the killed process group (for example by calling `os.setsid()`) and still holds the inherited stdout or stderr pipe. `_kill_and_wait` bounds its post-`kill_group` `await proc.wait()` with a short fixed `asyncio.timeout`; on expiry it closes the process transport so the escaped descendant's held pipe can no longer block the waiters. `SubprocessExec.run`'s exception path then cancels and gathers the outstanding capture tasks instead of waiting for their natural EOF, and still re-raises the original `TimeoutError` (seam timeout) or `CancelledError` (outer cancellation) unchanged.

## Why
`_kill_and_wait` (`squatch/seams.py:181-183`) calls `kill_group` and then awaits `proc.wait()` with no bound; `SubprocessExec.run`'s exception handler (`squatch/seams.py:151-157`) then awaits the capture tasks through `asyncio.gather` with no bound either. Both waits resolve only once asyncio's subprocess transport sees the child exited AND every captured pipe closed -- a descendant that escaped the killed group while still holding the inherited stdout pipe keeps both waits pending until that descendant exits on its own. This is the one kill path the seam's timeout and cancellation handling share, and it is also the path the kill verb's executor abort cancels through, so a hang here stalls a stage's terminal transition with nothing able to release it. Section 16 treats executed code as fenced, never trusted, so a daemonizing or hostile tool must not be able to stall the driver this way.

## Scope in
- The post-`kill_group` wait in `_kill_and_wait` and the capture-task cleanup in `SubprocessExec.run`'s exception path, both in `squatch/seams.py`.
- Regression tests in `tests/test_seams.py` covering a descendant that escapes the killed group and holds the inherited stdout pipe, for both the seam-timeout and outer-cancellation paths.

## Scope out
- The process-group kill signal itself (`kill_group`, `os.killpg`) and the `start_new_session` spawn binding -- unchanged.
- Any change to the seam's timeout budget, stuck-detection, or the kill verb's executor-abort call site.
- Filing the escaped pid anywhere (no logging seam is wired into `squatch/seams.py` today; out of scope for this fix).

## Scope fence
- squatch/seams.py
- tests/test_seams.py

## Acceptance criteria
- `_kill_and_wait` bounds its post-`kill_group` `await proc.wait()` with a short fixed `asyncio.timeout` and closes the process transport on expiry instead of continuing to wait, checked by `pytest tests/test_seams.py::test_timeout_bounds_when_a_descendant_escapes_with_an_open_pipe -q`.
- When that bound expires, `SubprocessExec.run`'s exception path cancels and gathers the outstanding capture tasks instead of awaiting their natural EOF, checked by `pytest tests/test_seams.py::test_timeout_bounds_when_a_descendant_escapes_with_an_open_pipe -q`.
- `SubprocessExec.run` still raises the original `TimeoutError` for a seam timeout, and the original `CancelledError` for an outer cancellation, even when a descendant has escaped the killed group, checked by `pytest tests/test_seams.py::test_timeout_bounds_when_a_descendant_escapes_with_an_open_pipe -q` and `pytest tests/test_seams.py::test_cancellation_bounds_when_a_descendant_escapes_with_an_open_pipe -q`.
- The existing kill-path behavior for a well-behaved child (no escaped descendant) is unchanged, checked by `pytest tests/test_seams.py -q`.

## Verification
```
pytest tests/test_seams.py::test_timeout_bounds_when_a_descendant_escapes_with_an_open_pipe -q
pytest tests/test_seams.py::test_cancellation_bounds_when_a_descendant_escapes_with_an_open_pipe -q
pytest tests/test_seams.py -q
```

## Regression
```
pytest tests/test_seams.py::test_timeout_bounds_when_a_descendant_escapes_with_an_open_pipe -q
```
- carries: tests/test_seams.py

## Definition of rejected
Stop and throw the branch away if bounding the wait requires touching `kill_group`'s signal semantics, the spawn/session binding, or any caller's timeout/stuck-budget configuration -- this ticket is confined to `_kill_and_wait` and the capture-task cleanup in `SubprocessExec.run`.

## Time budget
- expected: 45m
- stuck: 90m
