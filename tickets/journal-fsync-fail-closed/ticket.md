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
- squatch/journal.py
- squatch/effects.py
- tests/test_journal.py
- tests/test_fault_injection.py

## Goal
When `Journal.append` raises from the line write, `flush`, or `os.fsync`, the `Journal` instance marks itself broken and refuses every later `append` immediately, instead of leaving a process whose in-memory state silently disagrees with what already reached disk.

## Why
`Effects.run` (squatch/effects.py:56-64) grows its in-memory completed-key map only after `Journal.append` returns. `Journal.append` (squatch/journal.py:137-139) writes the line, flushes, and calls `os.fsync` with nothing catching a failure partway through. If `os.fsync` raises after the line is already written, the `effect_completion` record can be durable on disk while the running process's completed map still lacks the key. A caller that catches that exception and retries the same key in-process -- `Effects.run` called again on the same `Effects`/`Journal` instance -- would re-run an action the journal already records as complete. Restart replay is unaffected and already correct (tests/test_fault_injection.py pins it): a fresh `Journal`/`Effects` pair rebuilds the completed map from disk from scratch. The fix belongs at the one place that writes: once `append` has seen any exception from the write path, the instance should never again attempt a write or report success, so no caller anywhere can retry in-process past a durability failure whose outcome is unknown.

## Scope in
- `Journal.append` in `squatch/journal.py`: catch an exception raised by the line write, `flush`, or `os.fsync`, mark the instance broken, and re-raise the original exception.
- `Journal.append` in `squatch/journal.py`: when the instance is already marked broken, raise immediately before attempting any write, flush, or fsync, with a message stating the journal's durability is unknown and that the process must restart for replay to rebuild state from disk.
- A regression test in `tests/test_journal.py` that monkeypatches `os.fsync` to raise `OSError` once during an `effect_completion` append.

## Scope out
- Any change to `squatch/effects.py`: `Effects.run`'s in-process dedup logic is unchanged; it fails closed as a consequence of `Journal.append` failing closed, not through a second check in `Effects`.
- Any new fault-injection seam or harness fault point: the regression test monkeypatches `os.fsync` directly.
- Any change to restart/replay behavior (already correct, covered by `tests/test_fault_injection.py`).

## Scope fence
- squatch/journal.py
- tests/test_journal.py

## Acceptance criteria
- When `os.fsync` raises during an `effect_completion` append, `Journal.append` marks the instance broken and re-raises the original exception, checked by `python -m pytest tests/test_journal.py::test_append_fsync_failure_fails_closed -q`.
- After that failure, a second `Effects.run` call with the same key on the same `Effects` instance raises before invoking the action, checked by `python -m pytest tests/test_journal.py::test_append_fsync_failure_fails_closed -q`.
- After that failure, a later, unrelated `append` call on the same `Journal` instance also raises immediately without attempting a write, checked by `python -m pytest tests/test_journal.py::test_append_fsync_failure_fails_closed -q`.
- A fresh `Journal` plus `Effects` opened over the same directory after the failure replays the completed effect from disk and returns its recorded result without calling the action again, checked by `python -m pytest tests/test_journal.py::test_append_fsync_failure_fails_closed -q`.
- The existing restart-replay regression stays green, checked by `python -m pytest tests/test_fault_injection.py -q`.

## Verification
```
python -m pytest tests/test_journal.py::test_append_fsync_failure_fails_closed -q
python -m pytest tests/test_journal.py -q
python -m pytest tests/test_fault_injection.py -q
python -m pytest tests/test_effects.py -q
```

## Regression
```
python -m pytest tests/test_journal.py::test_append_fsync_failure_fails_closed -q
```
- carries: tests/test_journal.py

## Definition of rejected
Stop and throw the branch away if making `Journal.append` fail closed requires changing `Effects.run`'s dedup logic, adding a config knob, adding a harness fault-injection seam, or touching any file outside `squatch/journal.py` and its dedicated test.

## Time budget
- expected: 30m
- stuck: 60m
