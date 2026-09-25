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
- shakeout-stages

## Context
- squatch/driver.py
- squatch/llmeffect.py
- squatch/seams.py
- squatch/llm.py
- squatch/drain.py
- tests/test_driver.py
- tests/test_drain.py

## Plan contract
- section 19

## Goal
The driver shakeout group pins `squatch/driver.py`: unparseable or schema-invalid stage output exhausts the bounded re-prompt and terminals `invalid_artifact`, and a stage past its stuck budget is killed by the driver's `wait_for`, harvested, and terminals `timeout` while the drain proceeds to the next ticket -- re-confirming every prior group's entries before appending its own.

## Why
Section 19 names both members and their owner: the schema-invalid re-prompt loop and the per-stage `wait_for` stuck-budget kill are the Phase 0 driver's (section 5 invariant 2, section 15's seam ladder), so one group fences `squatch/driver.py` plus its test file. The discriminating observables are the exact effect-key count -- a bounded loop makes exactly `retry_cap + 1` calls under consecutive `call_seq` keys and a faked loop cannot -- and the `timeout` terminal preceded by the fake's abort with the harvest dir present, while the drain's next ticket still reaches `merged` in the same invocation (section 11.2's handler and section 18's park-and-continue).

## Scope in
A new member module `eval/shakeout/driver_group.py` with `GROUP` = `shakeout-driver` and `MEMBERS`: `schema_invalid_exhausts_reprompt` -- the fake review answers a verdict outside its vocabulary on every call; observable: exactly `caps.retry + 1` review effect completions under consecutive `call_seq` keys and the terminal `to: invalid_artifact`; expected `invalid_artifact:reprompt_exhausted`; detail `tickets/<stem>/attempts/<n>/harvest.json`. `stuck_budget_killed` -- one original `Bench` is built through the public `Bench.make(..., sleep=...)` seam with a fake sleep that advances its injected clock by the requested duration; a resisting `Hang` crosses a one-minute stuck budget, then the SAME bench's public `drain()` continues to a second green ticket without any private provenance steering; observable: `FakeLLM.aborted` is 1, the terminal `to: timeout`, `tickets/<stem>/attempts/<n>/harvest.json` committed, and the second ticket reaches `merged`; expected `timeout:killed_harvested_drain_continued`; detail `tickets/<stem>/attempts/<n>/harvest.json`. `eval/shakeout/registry.py`'s `GROUPS` gains `("shakeout-driver", "eval.shakeout.driver_group")` after the stages group. `tests/test_driver.py` gains one unit pin per observable where the existing tests carry none. The report is produced by this ticket's own `## Verification` with `--prior tickets/shakeout-stages/shakeout-report.json`.

## Scope out
No change to `squatch/driver.py` or any production module. No members owned by other modules. No hand-written entry, no edit of a prior group's entries, no wall-clock wait, no event-loop monkeypatch, and no call to a private `Bench` method: the stuck budget elapses through the merged clock/sleep seam and the fake's cancellation.

## Scope fence
- eval/shakeout/driver_group.py
- eval/shakeout/registry.py
- tests/test_driver.py

## Acceptance criteria
- In `tests/test_driver.py`, a stage scripted invalid on every call makes exactly `retry_cap + 1` calls under consecutive `call_seq` keys and returns `invalid_artifact`, and a resisting hang past the stuck budget is aborted before any terminal is recorded.
- `uv run python -m eval.shakeout run --outbox tickets/shakeout-driver --prior tickets/shakeout-stages/shakeout-report.json` exits 0 and writes `tickets/shakeout-driver/shakeout-report.json` whose prior entries are byte-identical to the stages group's report and whose two new entries are `shakeout-driver.schema_invalid_exhausts_reprompt` and `shakeout-driver.stuck_budget_killed`, both `green` true and `auditor` `green`.
- `uv run python -m eval.shakeout check tickets/shakeout-driver/shakeout-report.json` exits 0.
- `git diff --name-only main...shakeout-driver` lists `eval/shakeout/driver_group.py`, `eval/shakeout/registry.py`, and `tests/test_driver.py`, and no path under `tickets/`.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_driver.py tests/test_shakeout.py -q
uv run python -m eval.shakeout run --outbox tickets/shakeout-driver --prior tickets/shakeout-stages/shakeout-report.json
uv run python -m eval.shakeout check tickets/shakeout-driver/shakeout-report.json
git diff --name-only main...shakeout-driver
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` naming the member if the merged engine does not produce a member's stated observable through the public clock/sleep and bench APIs, if a prior group's committed entry cannot be re-confirmed byte-for-byte, if any file outside the fence must change, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 60m
- stuck: 120m
