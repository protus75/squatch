---
priority: P1
kind: bug
agent_tier: medium
agent_effort: medium
source: box:suggestion
state: draft
---

## Depends on
- none

## Context
- squatch/tickets.py
- tests/test_tickets.py

## Goal
A pending ticket's frontmatter carrying a non-string key (YAML 1.1 `yes:`/`no:`/`1:` style, or any other non-string mapping key) alongside an unknown string key is refused at the front door by `Intake.run()` with one `ticket_schema` finding naming the offending key and the closed-key paved road, the same as every other hand-authored shape defect, instead of crashing the whole intake pass with an unhandled `TypeError`.

## Why
`_lint_frontmatter` sorts `set(meta) - FRONTMATTER_KEYS` to report unknown keys, but YAML's safe loader turns bare `yes`/`no`/`on`/`off` into booleans and bare integers into ints, so a frontmatter mapping key does not have to be a string. Sorting a mix of `str` and `bool`/`int` raises `TypeError` before any finding is built, and `Intake.run()` only catches `ValueError` and `TicketLintError` from that path, so the crash escapes and stops the whole front door instead of refusing just the offending stem -- the same class of gap decision-000128 closed for structural and non-scalar-value frontmatter defects, but for a key-type crash that work did not cover.

## Scope in
Make `_lint_frontmatter` in `squatch/tickets.py` report every frontmatter key that is not a `str` as a `ticket_schema` finding naming that key's `repr`, before computing `sorted(set(meta) - FRONTMATTER_KEYS)`, so the unknown-key sort only ever receives string keys and a mixed-type frontmatter is refused instead of crashing `Intake.run()`.

## Scope out
No change to `FRONTMATTER_KEYS`, the closed `state`/`source`/`priority`/`kind`/`agent_tier`/`agent_effort`/`gate_bypass` vocab, any other `_lint_*` function, or any gate outside ticket frontmatter linting.

## Scope fence
- squatch/tickets.py
- tests/test_tickets.py

## Acceptance criteria
- `Intake.run()` refuses a ticket whose frontmatter carries a non-string key (for example YAML 1.1 `yes: x`) alongside an unknown string key (for example `tags: y`) with a `ticket_schema` finding naming the offending key, instead of raising `TypeError`, checked by `uv run pytest tests/test_tickets.py`.
- `tests/test_tickets.py`'s parametrized `test_hand_authored_shape_is_refused_at_the_front_door_not_crashed` gains a case adding `yes: x` and `tags: y` to the frontmatter, asserting the same results as every other case in that parametrization -- nothing committed, exactly one refusal carrying `ticket_schema` with a non-empty paved road, HEAD unchanged, and an empty journal -- checked by `uv run pytest tests/test_tickets.py`.
- The full suite stays green, checked by `uv run pytest`.

## Verification
```
uv run pytest tests/test_tickets.py
uv run pytest
```

## Regression
```
uv run pytest tests/test_tickets.py -k test_hand_authored_shape_is_refused_at_the_front_door_not_crashed
```
- carries: tests/test_tickets.py

## Definition of rejected
If the minimal fix requires widening `FRONTMATTER_KEYS`, changing any closed frontmatter vocabulary, or touching a `_lint_*` function or gate outside `_lint_frontmatter`'s unknown-key sort, stop and file a Suggestion Box item instead of expanding scope.

## Time budget
- expected: 20m
- stuck: 60m
