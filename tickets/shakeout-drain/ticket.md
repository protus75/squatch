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
- shakeout-providers

## Context
- squatch/drain.py
- squatch/runner.py
- squatch/tickets.py
- tests/test_drain.py
- tests/test_drain_upgrade.py

## Plan contract
- section 19
- section 18
- section 11
- section 13

## Goal
The drain shakeout group pins `squatch/drain.py`: a ticket red on attempt one and green on attempt two merges in ONE drain invocation with exactly one `retry` draw, and a premise-failed stem is skipped across invocations until its committed `ticket.md` changes, then runs -- re-confirming every prior group's entries before appending its own.

## Why
Section 19 names both members, and section 18 fixes their owner and shape: the drain re-offers a parked stem at provisional quiescence with one retry unit drawn per re-offer, re-evaluating quiescence after every re-offer merge, and a `premise_failed` stem stays parked until its ticket-plane `ticket.md` commit changes -- re-asking an unchanged ticket replays a judgment, not work (section 2). The discriminating observables are the journal's shape inside one invocation -- `gate_failed` for run 0, one `cap_consumed` naming `retry`, `merged` for run 1 -- and, for the park, the absence of any new `running` across a second invocation followed by its presence after a `ticket.md` content commit, which a faked skip keyed on anything but the committed blob cannot reproduce.

## Scope in
A new member module `eval/shakeout/drain_group.py` with `GROUP` = `shakeout-drain` and `MEMBERS`: `red_then_green_one_invocation` -- the fake implementer fails a `## Verification` command on run 0 and passes on run 1; observable: within one `bench.drain()` exit 0, the journal holds `to: gate_failed` for run 0, exactly one `cap_consumed` with `cap: retry`, and `to: merged` for run 1; expected `merged:one_invocation_one_retry`; detail `tickets/<stem>/attempts/0/harvest.json`. `premise_park_released_by_edit` -- the fake answers `premise_failed` on run 0; observable: a second `bench.drain()` journals no new `running` for the stem and reports it parked with the source-keyed road, and a third drain after a committed `ticket.md` content change journals `running` with `run_seq` 1; expected `premise_failed:skipped_until_edit`; detail `tickets/<stem>/run.md`. `eval/shakeout/registry.py`'s `GROUPS` gains `("shakeout-drain", "eval.shakeout.drain_group")` after the providers group. `tests/test_drain.py` gains a unit pin for each observable where the existing tests carry none. The report is produced by this ticket's own `## Verification` with `--prior tickets/shakeout-providers/shakeout-report.json`.

## Scope out
No change to `squatch/drain.py` or any production module. No self-upgrade re-exec member (its own test file pins it). No hand-written entry, no edit of a prior group's entries.

## Scope fence
- eval/shakeout/drain_group.py
- eval/shakeout/registry.py
- tests/test_drain.py

## Acceptance criteria
- In `tests/test_drain.py`, a stem red on run 0 and green on run 1 merges in one invocation with exactly one `retry` draw, and a `premise_failed` stem is not re-dispatched by a second invocation but is by a third after a committed `ticket.md` content change.
- `uv run python -m eval.shakeout run --outbox tickets/shakeout-drain --prior tickets/shakeout-providers/shakeout-report.json` exits 0 and writes `tickets/shakeout-drain/shakeout-report.json` whose prior entries are byte-identical to the providers group's report and whose two new entries are `shakeout-drain.red_then_green_one_invocation` and `shakeout-drain.premise_park_released_by_edit`, both `green` true and `auditor` `green`.
- `uv run python -m eval.shakeout check tickets/shakeout-drain/shakeout-report.json` exits 0.
- `git diff --name-only main...shakeout-drain` lists `eval/shakeout/drain_group.py`, `eval/shakeout/registry.py`, and `tests/test_drain.py`, and no path under `tickets/`.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_drain.py tests/test_shakeout.py -q
uv run python -m eval.shakeout run --outbox tickets/shakeout-drain --prior tickets/shakeout-providers/shakeout-report.json
uv run python -m eval.shakeout check tickets/shakeout-drain/shakeout-report.json
git diff --name-only main...shakeout-drain
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` naming the member if the merged engine does not produce a member's stated observable, if the bench as landed cannot run three drains over one state dir with a ticket-plane commit between them, if a prior group's committed entry cannot be re-confirmed byte-for-byte, if any file outside the fence must change, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 60m
- stuck: 120m
