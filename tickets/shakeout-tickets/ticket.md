---
state: confirmed
source: seed
priority: P1
kind: chore
# section 19 pre-ladder tier rule: every code-bearing Phase 2 seed runs at the
# HIGH tier until the escalation ladder merges; effort stays at the default.
agent_tier: high
agent_effort: medium
---
## Depends on
- shakeout-report

## Context
- squatch/tickets.py
- squatch/drain.py
- squatch/runner.py
- tests/test_tickets.py
- tests/test_drain.py

## Plan contract
- section 19
- section 13
- section 15

## Goal
The first shakeout battery group pins `squatch/tickets.py`: a planted bad-schema ticket never dispatches, is refused at intake with a `ticket_schema` finding, and the drain still reaches quiescence -- its entries machine-produced into this run's outbox as the first `shakeout-report.json`.

## Why
Section 19 seeds the battery as one chained deliverable per owning production module, each member naming its planted fault, its single discriminating observable, and the artifact carrying the human-readable detail, with entries machine-produced to the OUTBOX and lifted by the one stage-terminal lift path -- never hand-authored. The bad-schema member is the battery's first because the intake grammar gate (section 13) is the earliest point a synthetic ticket can fail, and the discriminating observable is a NEGATIVE one: a correct engine journals no `running` transition for the stem, while a faked run that dispatches anyway cannot avoid one. This group has no predecessor, so it carries no `--prior` and its report is the base every later group re-confirms.

## Scope in
A new member module `eval/shakeout/tickets_group.py` with `GROUP` = `shakeout-tickets` and `MEMBERS`: `bad_schema` -- fault: a `tickets/bad-schema/ticket.md` committed on the bench's main with a `priority` outside the closed vocabulary and no `## Verification`; observable: after `bench.drain()` exits 0, the journal holds NO `state_transition` for `bad-schema` and one green ticket beside it reaches `merged`; expected `held:no_running_transition`; detail: the drain's `held:` report line and the `ticket_schema` findings. `eval/shakeout/registry.py`'s `GROUPS` gains `("shakeout-tickets", "eval.shakeout.tickets_group")` as its first entry. `tests/test_tickets.py` gains the battery's unit pin beside the intake tests: the drain's scan holds a committed ticket that fails lint with the finding's paved road, never dispatching it. The report is produced by this ticket's own `## Verification`: `uv run python -m eval.shakeout run --outbox tickets/shakeout-tickets` writes `tickets/shakeout-tickets/shakeout-report.json` into the worktree outbox, which the Check lift commits.

## Scope out
No second member, no change to `squatch/tickets.py` or `squatch/drain.py` (a gap in them is `premise_failed`, never patched here), no hand-written report entry, no `--prior` (first group). No change to the bench, the schema, or the runner beyond the registry entry.

## Scope fence
- eval/shakeout/tickets_group.py
- eval/shakeout/registry.py
- tests/test_tickets.py

## Acceptance criteria
- In `tests/test_tickets.py`, a committed ticket with `priority: P9` on the plane is reported `held:` by the drain with the `ticket_schema` finding and journals no `state_transition`.
- `uv run python -m eval.shakeout run --outbox tickets/shakeout-tickets` exits 0 and writes `tickets/shakeout-tickets/shakeout-report.json` with exactly one entry, `shakeout-tickets.bad_schema`, `green` true and `auditor` `green`.
- `uv run python -m eval.shakeout check tickets/shakeout-tickets/shakeout-report.json` exits 0.
- `git diff --name-only main...shakeout-tickets` lists `eval/shakeout/tickets_group.py`, `eval/shakeout/registry.py`, and `tests/test_tickets.py`, and no path under `tickets/`.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_tickets.py tests/test_shakeout.py -q
uv run python -m eval.shakeout run --outbox tickets/shakeout-tickets
uv run python -m eval.shakeout check tickets/shakeout-tickets/shakeout-report.json
git diff --name-only main...shakeout-tickets
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` if the bench as landed cannot commit a lint-failing ticket onto its main, if the drain as landed dispatches a lint-failing committed ticket, if any file outside the fence must change, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 45m
- stuck: 90m
