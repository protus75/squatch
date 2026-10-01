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
- squatch/runner.py
- squatch/journal.py
- tests/test_cli.py

## Goal
`Runner.session` in `squatch/runner.py` turns a `JournalCorruption` raised anywhere in its locked body -- the `supervised_merge_holds(journal.read())` fold, `reconcile`, and `Intake.run` -- into the same `Refusal` it already raises for a corrupt `Journal(...)` construction, so every verb entering a session (`run`, `confirm`, `reject`, `drain`) exits `EXIT_REFUSED` with the existing journal-corruption message and paved road, never an uncaught traceback.

## Why
`Journal.__init__` only validates segment names and the active segment's first line (`_first_event_time`), so it cannot see a corrupt record sitting on a later line of any segment. That record is first parsed when something actually iterates `journal.read()`, and inside `session()` (`squatch/runner.py:169-195`) the only `except JournalCorruption` wraps the `Journal(...)` call at line 180, not the `with journal:` block beneath it. A `JournalCorruption` raised by the `supervised_merge_holds(journal.read())` fold at line 186, by `reconcile`, or by `Intake.run` therefore escapes the `async with self.session()` context entirely and surfaces at the CLI's `except Refusal` (`squatch/__main__.py:128`) as a bare traceback -- the class section 18 reserves for a non-ok ticket terminal (exit 1), not the engine-plane refusal (exit 2) this is. `status` and other read-only verbs already refuse the identical corruption with the refusal exit, so this is purely a gap in where the writer verbs' lock-held entry catches it. Nothing is journaled before the first read, and `lock.release()` in the `finally` still runs, so the fix is confined to widening the existing single wrap around the locked body -- no second catch site, no new exception class.

## Scope in
- Restructure `Runner.session` so the existing `except JournalCorruption -> Refusal` conversion covers every record read between the lock being acquired and the session's `yield`, including the `supervised_merge_holds(journal.read())` fold, `reconcile`, and `Intake.run`, not only the `Journal(...)` constructor.
- A test in `tests/test_cli.py` that journals one valid event, appends a well-formed JSON line that is not a valid event envelope to the active segment, invokes `run <stem>`, and asserts the refusal exit code, the `refused: journal corruption:` message prefix, and that the lock is released afterward (a following CLI invocation in the same checkout succeeds in acquiring it).

## Scope out
- `Journal.__init__`, `_first_event_time`, `_truncate_torn_tail`, and `_read_segment` in `squatch/journal.py` (unchanged; they already raise `JournalCorruption` correctly, this ticket only moves where the runner catches it).
- Any `JournalCorruption` raised by code that runs AFTER `session()` yields control back to the verb bodies (`run`, `confirm`, `reject`'s own `journal.read()` calls, or anything inside `dispatch`/the stage pipeline) -- out of scope for this wrap; the triage confines the fix to the session entry body.
- `squatch/__main__.py`'s `_locked` and its CLI composition (unchanged; the fix is entirely inside `Runner.session`).

## Scope fence
- squatch/runner.py
- tests/test_cli.py

## Acceptance criteria
- A `JournalCorruption` raised by `supervised_merge_holds(journal.read())`, by `reconcile`, or by `Intake.run` inside `Runner.session`'s locked body is converted to the same `Refusal` message and paved road the constructor path already uses, checked by `tests/test_cli.py`.
- Invoking `run <stem>` against a journal whose active segment has a valid first record and a malformed later record exits `EXIT_REFUSED` (2), not a traceback, checked by `tests/test_cli.py`.
- The lock is released when corruption is caught mid-session: a subsequent CLI invocation in the same checkout can acquire it, checked by `tests/test_cli.py`.
- `squatch/runner.py` still raises `JournalCorruption` from exactly the same sites in `squatch/journal.py` as before (no new catch site added elsewhere), checked by reading the diff against `## Scope fence`.

## Verification
```
pytest tests/test_cli.py -k journal_read_corruption -q
pytest tests/test_cli.py -q
```

## Regression
```
pytest tests/test_cli.py -k journal_read_corruption -q
```
- carries: tests/test_cli.py

## Definition of rejected
Stop and throw the branch away if making this pass requires catching `JournalCorruption` anywhere outside `Runner.session`'s locked body (for example in `dispatch`, the stage pipeline, or `squatch/__main__.py`'s `_locked`), or requires changing what `squatch/journal.py` raises or when -- this ticket is a single wrap's placement, not a second catch site or a journal-reader change.

## Time budget
- expected: 30m
- stuck: 90m
