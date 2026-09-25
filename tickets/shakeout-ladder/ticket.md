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
- shakeout-drain

## Context
- squatch/runner.py
- squatch/drain.py
- squatch/config.py
- tests/test_drain.py
- tests/test_terminal.py

## Plan contract
- section 19

## Goal
The last shakeout battery group pins `squatch/ladder.py`: K identical terminal reasons short-circuit past a same-rung re-offer to the ladder while rungs remain and to the Reject queue when none do -- re-confirming every prior group's entries before appending its own, so its committed `shakeout-report.json` is the cumulative copy the Phase 2 exit reads.

## Why
Section 19 names the member "K identical terminal reasons short-circuit per section 11.4" and makes the LAST group's ticket dir the resting place of the cumulative report that the exit ticket's transitive `depends` locates; section 11.4 fixes the rule -- K consecutive attempts ending with the identical terminal reason climb the capability ladder instead of re-running at the same rung, and short-circuit to Reject only when the ladder is exhausted -- and `escalation-ladder` landed it in `squatch/ladder.py`, the module this group fences. The discriminating observables are the `rung` body on the K-th re-offer's retry draw under a multi-model routing fixture and the `routed: reject_queue` marker on the K-th terminal under a single-model fixture where the ladder is exhausted at the start -- a faked short-circuit cannot place the rung on the draw the drain journals.

## Scope in
A new member module `eval/shakeout/ladder_group.py` with `GROUP` = `shakeout-ladder` and `MEMBERS`: `identical_terminals_climb` -- under a bench routing fixture whose `implement` surface resolves distinct models at `medium` and `high`, the fake fails the same `## Verification` command on every run; observable: the third consecutive `gate_failed` with one reason is followed by a retry `cap_consumed` whose body carries a `rung` above the authored tier, and no fourth same-rung re-offer precedes it; expected `identical:climbed`; detail `tickets/<stem>/diagnosis.json`. `identical_terminals_reject_when_exhausted` -- under a single-model fixture with the ticket authored at the top rung, the same fault; observable: the third identical terminal carries `routed: reject_queue` with a reason naming the exhausted ladder, and the drain reports the stem under `reject queue:`; expected `identical:rejected_exhausted`; detail `tickets/<stem>/diagnosis.json`. `eval/shakeout/registry.py`'s `GROUPS` gains `("shakeout-ladder", "eval.shakeout.ladder_group")` after the drain group, as its last entry. `tests/test_ladder.py` gains a unit pin for each observable where the existing tests carry none; read `squatch/ladder.py`, `squatch/reject.py`, and `tests/test_ladder.py` in the worktree (they land with the `depends` and did not exist when this seed was authored). The report is produced by this ticket's own `## Verification` with `--prior tickets/shakeout-drain/shakeout-report.json`, and `check` over it is the whole battery's green.

## Scope out
No change to `squatch/ladder.py`, `squatch/reject.py`, or any production module. No oscillation or same-wall member (their unit tests landed with the ladder). No hand-written entry, no edit of a prior group's entries, no second report path, no copy of the report anywhere but this ticket's outbox.

## Scope fence
- eval/shakeout/ladder_group.py
- eval/shakeout/registry.py
- tests/test_ladder.py

## Acceptance criteria
- In `tests/test_ladder.py`, three consecutive identical `gate_failed` terminals under a multi-model fixture yield a retry draw carrying a `rung`, and under a top-rung single-model fixture yield a `routed: reject_queue` terminal naming the exhausted ladder.
- `uv run python -m eval.shakeout run --outbox tickets/shakeout-ladder --prior tickets/shakeout-drain/shakeout-report.json` exits 0 and writes `tickets/shakeout-ladder/shakeout-report.json` whose prior entries are byte-identical to the drain group's report and whose two new entries are `shakeout-ladder.identical_terminals_climb` and `shakeout-ladder.identical_terminals_reject_when_exhausted`, both `green` true and `auditor` `green`.
- `uv run python -m eval.shakeout check tickets/shakeout-ladder/shakeout-report.json` exits 0 with every registered member of every group green.
- `git diff --name-only main...shakeout-ladder` lists `eval/shakeout/ladder_group.py`, `eval/shakeout/registry.py`, and `tests/test_ladder.py`, and no path under `tickets/`.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_ladder.py tests/test_shakeout.py -q
uv run python -m eval.shakeout run --outbox tickets/shakeout-ladder --prior tickets/shakeout-drain/shakeout-report.json
uv run python -m eval.shakeout check tickets/shakeout-ladder/shakeout-report.json
git diff --name-only main...shakeout-ladder
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` naming the member if the merged engine does not produce a member's stated observable, if the bench as landed cannot run under a routing fixture other than the instance's, if a prior group's committed entry cannot be re-confirmed byte-for-byte, if any file outside the fence must change, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 45m
- stuck: 90m
