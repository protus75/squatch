---
priority: P2
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
`RESERVED_STEMS` in `squatch/tickets.py` reserves `main` alongside `decisions` and `retro`, and `_STEM_ROAD`'s paved road names `main` as reserved too. A pending `tickets/main/ticket.md` is refused at the front door by `Intake.run()` with one `ticket_schema` finding, nothing committed and HEAD unchanged, and `new_ticket`'s stem check raises the same `ValueError` for `main` that it already raises for `decisions` and `retro`. Every stem valid today stays valid.

## Why
`STEM` matches `main`, and `RESERVED_STEMS` currently reserves only `decisions` and `retro`, so a ticket stem of `main` passes every grammar check `lint_ticket` runs. `Stages._workspace` treats the stem as its branch name: for a ticket named `main` it calls `branch_delete` on the engine's own integration branch before `worktree_add`, either failing as a raw git error when `main` is checked out or actually deleting `main` otherwise. Either way the run stops with a generic fault instead of a named intake refusal carrying a paved road, and the stem can be re-offered into the same failure. `main` is a fixed engine name exactly like the other two reserved stems, so widening the closed reserved set is the fail-closed fix; a general check for any pre-existing branch is not needed, since every other stem's branch belongs to the engine by design.

## Scope in
Add `main` to `RESERVED_STEMS` and to `_STEM_ROAD`'s paved-road text in `squatch/tickets.py`, so every check that already reads `RESERVED_STEMS` (`lint_ticket`, `TicketSchemaGate.check`, `new_ticket`) refuses `main` the same way it refuses `decisions` and `retro`.

## Scope out
No change to `Stages._workspace`, branch-deletion or workspace-teardown logic, or any check beyond the closed `RESERVED_STEMS` set; no general pre-existing-branch check for other stems.

## Scope fence
- squatch/tickets.py
- tests/test_tickets.py

## Acceptance criteria
- `RESERVED_STEMS` contains exactly `decisions`, `retro`, and `main`, checked by `uv run pytest tests/test_tickets.py`.
- A pending `tickets/main/ticket.md` is refused by `Intake.run()` with one `ticket_schema` finding, `result.committed == ()`, and HEAD unchanged, checked by a new `tests/test_tickets.py` case.
- `new_ticket(repo, "main", fs=fs)` raises `ValueError` naming `main` as a reserved/invalid stem, checked by `uv run pytest tests/test_tickets.py`.
- Every stem valid today (for example `widget-parser`) still lints and intakes unchanged, checked by `uv run pytest tests/test_tickets.py`.
- The full suite stays green, checked by `uv run pytest`.

## Verification
```
uv run pytest tests/test_tickets.py
uv run pytest
```

## Regression
```
uv run pytest tests/test_tickets.py -k test_reserved_stem_main_is_refused_at_the_front_door
```
- carries: tests/test_tickets.py

## Definition of rejected
If refusing `main` requires touching `Stages._workspace`, branch-deletion/teardown behavior, or any check outside the closed `RESERVED_STEMS` set, stop and file a Suggestion Box item instead of widening scope.

## Time budget
- expected: 20m
- stuck: 60m
