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
- shakeout-tickets
- verification-attribution

## Context
- squatch/stages.py
- squatch/runner.py
- squatch/drain.py
- squatch/redact.py
- squatch/git.py
- tests/test_drain.py
- tests/test_terminal.py

## Plan contract
- section 19
- section 11
- section 7
- section 9
- section 6

## Goal
The stage-layer shakeout group pins `squatch/stages.py`: scope escape, false premise, a branch-only red command, a pre-existing base red, an empty committed diff, a review reject, the criteria-position re-entry of review findings, a timed-out attempt's dead ends visible to the next attempt, and a planted secret reaching no ticket-plane artifact all reach their exact terminal or artifact field with zero human input, re-confirming the tickets group's entry before appending its own.

## Why
Section 19 names these members and the module they pin: the scope-fence, verification, and run-record gates, the Review stage, the prior-attempts render, and the outbox lift are all the stage layer's (section 9's ownership law), so one group fences `squatch/stages.py` plus its test file. Each member's observable is the terminal reason code or artifact field a correct engine produces and a faked run cannot: the gate code on a `gate_failed` terminal, the `premise_failed` terminal, the `attribution` field of a `checks.json` entry (section 7's base-diff law, landed by `verification-attribution`, which this group therefore depends on), the presence of a prior finding inside the criteria-position block of the second attempt's spooled prompt (section 11.2), the dead-ends text of attempt one's run record inside attempt two's prompt, and the ABSENCE of a planted secret from every committed ticket-plane file (section 6's redaction seam). The double gate re-runs the tickets group's member first and refuses a differing entry.

## Scope in
A new member module `eval/shakeout/stages_group.py` with `GROUP` = `shakeout-stages` and `MEMBERS`, each planting its fault through the bench's fake implement subprocess or scripted `FakeLLM` and observing one field: `scope_escape` -- the fake implementer commits a file outside the fence; observable: the terminal `gate_failed` whose findings carry code `scope_fence`; expected `gate_failed:scope_fence`; detail `tickets/<stem>/checks.json`. `premise_false` -- the fake answers `premise_failed`; observable: the terminal `to: premise_failed`; expected `premise_failed`; detail `tickets/<stem>/run.md`. `branch_only_red` -- a `## Verification` command green at the base and red on the branch; observable: `gate_failed` with a `verification` finding whose `checks.json` entry carries `attribution: branch`; expected `gate_failed:verification:branch`; detail `tickets/<stem>/checks.json`. `base_red_excused` -- a command red at the base and on the branch with an otherwise green diff; observable: the run reaches Review, the entry carries `attribution: base` and a `filed` box id, and no `cap_consumed` names the stem; expected `check_passed:attribution_base`; detail the filed box message. `empty_diff` -- the fake implementer commits nothing and answers `implemented`; observable: `gate_failed` with a `verification` finding on the empty diff; expected `gate_failed:verification:empty_diff`; detail `tickets/<stem>/checks.json`. `review_reject` -- review scripted `snag`; observable: the terminal `gate_failed` carrying the review findings and `tickets/<stem>/review.md` pinned `snag`; expected `gate_failed:review_snag`; detail `tickets/<stem>/review.md`. `reject_reentry_criteria_position` -- after `review_reject`, the same drain re-offers the stem; observable: attempt two's spooled Implement prompt carries the prior finding's message inside the criteria-position findings block and not elsewhere; expected `reentry:criteria_position`; detail `<state_dir>/spools/<stem>/1/`. `timeout_dead_ends` -- attempt one hangs past a small stuck budget after writing a `run.md` whose `## Dead ends` names a marker; observable: attempt one terminals `timeout` and attempt two's prompt carries the marker inside the prior-attempts block; expected `timeout:dead_ends_rendered`; detail `tickets/<stem>/attempts/0/run.md`. `secret_not_persisted` -- the bench config declares a provider `auth` env var whose value the fake implementer echoes into `run.md` and stdout; observable: no committed file under `tickets/<stem>/` and no journal body carries the value, the redaction token appears in `run.md`; expected `secret:redacted_everywhere`; detail `tickets/<stem>/run.md`. `eval/shakeout/registry.py`'s `GROUPS` gains `("shakeout-stages", "eval.shakeout.stages_group")` after the tickets group. `tests/test_stages.py` gains one unit pin per member's observable where the existing tests carry none. The report is produced by this ticket's own `## Verification` with `--prior tickets/shakeout-tickets/shakeout-report.json`, the double gate re-confirming the tickets group's entry.

## Scope out
No change to `squatch/stages.py` or any production module (a member whose observable the merged engine does not produce is `premise_failed`, never patched here). No members owned by other modules (driver, reconcile, merge, providers, drain, ladder groups follow). No hand-written entry, no edit of a prior group's entries, no second report path.

## Scope fence
- eval/shakeout/stages_group.py
- eval/shakeout/registry.py
- tests/test_stages.py

## Acceptance criteria
- In `tests/test_stages.py`, each of the nine members' observables has a unit pin driven through the production `Stages`: the `scope_fence` code, the `premise_failed` delivery, the `attribution` values `branch` and `base`, the empty-diff finding, the `snag` review delivery, the criteria-position block of a re-entry render, the prior-attempts block carrying a prior run record's dead ends, and the redaction token in a lifted `run.md`.
- `uv run python -m eval.shakeout run --outbox tickets/shakeout-stages --prior tickets/shakeout-tickets/shakeout-report.json` exits 0 and writes `tickets/shakeout-stages/shakeout-report.json` whose first entry is byte-identical to the tickets group's and whose remaining nine entries are `shakeout-stages.scope_escape`, `premise_false`, `branch_only_red`, `base_red_excused`, `empty_diff`, `review_reject`, `reject_reentry_criteria_position`, `timeout_dead_ends`, `secret_not_persisted`, every entry `green` true and `auditor` `green`.
- `uv run python -m eval.shakeout check tickets/shakeout-stages/shakeout-report.json` exits 0.
- `git diff --name-only main...shakeout-stages` lists `eval/shakeout/stages_group.py`, `eval/shakeout/registry.py`, and `tests/test_stages.py`, and no path under `tickets/`.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_stages.py tests/test_shakeout.py -q
uv run python -m eval.shakeout run --outbox tickets/shakeout-stages --prior tickets/shakeout-tickets/shakeout-report.json
uv run python -m eval.shakeout check tickets/shakeout-stages/shakeout-report.json
git diff --name-only main...shakeout-stages
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` naming the member if the merged engine does not produce a member's stated observable, if the bench as landed cannot plant a fault a member needs (a hanging fake, a base-red command, a provider `auth` value), if the tickets group's committed entry cannot be re-confirmed byte-for-byte, if any file outside the fence must change, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 90m
- stuck: 180m
