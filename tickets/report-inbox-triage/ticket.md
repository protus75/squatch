---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- bug-gate-grammar

## Context
- squatch/box.py
- tests/test_box.py

## Plan contract
- section 20

## Goal
Intake bounded host reports and turn them into regression tickets.

## Why
Fixture-host evidence needs durable custody before sequential triage can author a bug ticket.

## Scope in
Enforce the version-1 report schema, metadata-first 1 MiB replay-file and 64 KiB log-excerpt caps, copy bounded evidence into durable Box custody before recording the message, wire the daemon consumer, and make sequential triage author `kind: bug` tickets whose evidence and `## Regression` survive intake. Daemon/Author roots, `squatch/triage.py`, their large tests, and delimiter-carrying `tests/test_triage.py` are measured on-demand inspection exceptions; the Box seam and focused `tests/test_box.py` are Context.

## Scope out
Do not retain unbounded evidence, bypass Box custody, or use the delimiter-carrying triage test as Context.

## Scope fence
- squatch/inbox.py
- squatch/box.py
- squatch/triage.py
- squatch/author.py
- squatch/daemon.py
- tests/test_box.py
- tests/test_triage.py
- tests/test_author.py
- tests/test_inbox.py

## Acceptance criteria
- `tests/test_inbox.py` proves version-1 reports validate metadata before bounded evidence replay.
- `tests/test_inbox.py` proves replay files cap at 1 MiB and log excerpts cap at 64 KiB before durable Box recording.
- `tests/test_triage.py` proves sequential triage authors `kind: bug` tickets retaining evidence and `## Regression`.

## Verification
```
uv run pytest tests/test_inbox.py -q
uv run pytest tests/test_box.py tests/test_triage.py tests/test_author.py -q
uv run pytest -q
```

## Definition of rejected
Reject unbounded custody, evidence lost during triage, missing bug regression grammar, or a fence violation.

## Time budget
- expected: 75m
- stuck: 150m
