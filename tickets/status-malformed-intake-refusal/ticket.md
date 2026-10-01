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
- squatch/status.py
- squatch/__main__.py
- squatch/journal.py
- tests/test_status.py

## Goal
When `project` in `squatch/status.py` folds an intake-signal event whose body is missing `source`, `state`, or `commit`, `squatch status` exits with the engine-plane refusal code and prints a `journal corruption` refusal naming the event's ticket and the missing field, instead of letting a bare `KeyError` escape as a raw traceback. The refusal follows the same paved road the existing journal-read and box-corruption refusals in `_status` (`squatch/__main__.py`) already use: a corrupt record is never skipped, so the operator is told to inspect the named record. Every well-formed journal still projects unchanged.

## Why
The module contract at the top of `squatch/__main__.py` says nothing reaches the operator as a raw traceback, and `main` catches only `Refusal`. `_status` already turns `JournalCorruption` from `read_events` and `BoxCorruption` from `project` into named refusals at their respective call sites. But the intake fold in `project` (`squatch/status.py:73-74`) indexes `e.body["source"]`, `e.body["state"]`, and `e.body["commit"]` directly, so a signal body missing one of them, whether from a hand-edited journal or one written by an older engine, raises an uncaught `KeyError` instead of a refusal with a paved road.

## Scope in
- `project` in `squatch/status.py`: validate the intake-signal body at the one read site (status.py:73-74) and raise `JournalCorruption` naming the event's ticket and the missing field when `source`, `state`, or `commit` is absent.
- `_status` in `squatch/__main__.py`: catch `JournalCorruption` at its existing `project(...)` call (alongside the `BoxCorruption` catch already there) and raise the same `journal corruption` `Refusal` shape the `read_events` call already raises.
- A regression test in `tests/test_status.py` projecting a journal holding one intake signal missing a required key and asserting `main(["status"])` returns the refusal exit code and prints the refusal, not a traceback.

## Scope out
- `effects-completion-result-corruption` and `journal-event-type-corruption` (the same kind of bare-`KeyError`/bare-`TypeError` fix in `squatch/effects.py` and `squatch/journal.py`; not this projection).
- Any change to the `state_transition` or `effect_completion` folding branches of `project`, which do not index these fields.
- Any change to the journal-read refusal already wired at `read_events` in `_status`.

## Scope fence
- squatch/status.py
- squatch/__main__.py
- tests/test_status.py

## Acceptance criteria
- An intake-signal event body missing `source`, `state`, or `commit` causes `project(...)` to raise `JournalCorruption` naming the event's ticket and the missing field, checked by `tests/test_status.py`.
- `main(["status"])` run against a journal containing such an event exits with the refusal exit code and prints a `journal corruption` refusal naming the ticket and missing field, never a traceback, checked by `tests/test_status.py`.
- A journal whose intake signals all carry `source`, `state`, and `commit` still projects the same `Status` as before this change, checked by `tests/test_status.py`.

## Verification
```
pytest tests/test_status.py -q
pytest tests/test_cli.py -q
```

## Regression
```
pytest tests/test_status.py -k malformed_intake -q
```
- carries: tests/test_status.py

## Definition of rejected
Stop and throw the branch away if fixing this requires changing the `Intaken`/`Status` dataclass shape, changing any other fold branch in `project`, or touching a file outside `squatch/status.py`, `squatch/__main__.py`, and `tests/test_status.py`.

## Time budget
- expected: 25m
- stuck: 50m
