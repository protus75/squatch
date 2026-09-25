---
state: confirmed
source: seed
priority: P1
kind: feature
# section 19 names every PHASE-EXIT seed KNOWN-HARD: it bundles a multi-read
# exit test with the next phase's first core batch, the shape that oscillates
# across attempts, so it starts high/high; the citing evidence is plan
# section 19, cited below.
agent_tier: high
agent_effort: high
---
## Depends on
- shakeout-ladder

## Context
- squatch/tickets.py
- squatch/drain.py
- squatch/stages.py
- squatch/config.py
- config.yaml
- tests/test_seeded_phase2.py
- tests/test_tickets.py

## Plan contract
- section 19

## Goal
Phase 2 is read closed and Phase 3 is seeded: this ticket dispatches only after every Phase 2 seed merged (its transitive `depends`), its Implement re-reads the two remaining exit criteria from committed artifacts through a merged test, and the same Implement authors Phase 3's first foundational core batch plus one `phase3-continue` seeding ticket as `confirmed` `ticket.md` files in its worktree's tickets plane, reviewed at its own Check stage and lifted to main by the seed path, eligible in the same drain invocation.

## Why
Section 19 fixes the phase boundary as three obligations read from evidence that outlives its producer: dependency completion is NOT a journal read -- every Phase 2 seed is a transitive `depends` of this stem, so the drain cannot dispatch it until all of them merged and its own dispatch IS that proof; the battery read is over the COMMITTED cumulative `shakeout-report.json` resting in the last group's ticket dir, machine-produced by the group runs and lifted by the one lane (emitters: the eight `shakeout-*` groups over `shakeout-report`'s machinery); the auditor read is over the auditor's Check-lane `checks.json` (emitter: the ordinary Check lane over `invariant-auditor`'s merged code) and the report's per-member auditor field. An exit read realized as a merged TEST runs at Check and on merged main where only committed artifacts exist, so it reads those artifacts and never the live journal, and this run's own Check-lane `checks.json` is the phase report -- machine-produced, lane-lifted, never hand-committed. Seeding is core-first and bounded: the batch is at most `seeding.max_seeds_per_admission` files, its seed definitions come from ONE named source -- the Phase 3 bullet's own Seeding partition in section 19 -- which this ticket reads and never edits, each seed `depends` on this stem so Phase 3 cannot start before Phase 2's exit merges (the mechanical meaning of "do not start a phase until the previous exit is met"), and a thin bullet is a PLAN defect: this ticket then answers `premise_failed` naming it, never inventing the partition inline. Seeds reach main only through the seed path `requisition-review-seed` landed -- reviewed at this Check, never on this branch -- and the drain's after-every-merge re-scan (section 18) makes them eligible in the same invocation. This is the first self-hosted seeding step, so it ships its own per-batch named-stem test file in the idiom of `tests/test_seeded_phase2.py`.

## Scope in
Implement performs, in order: (1) the exit READ as a new merged test `tests/test_phase2_exit.py` over committed artifacts only: `tickets/shakeout-ladder/shakeout-report.json` validates as `ShakeoutReport`, its `groups` are exactly the eight battery groups in chain order, and every member of the CLOSED list below is present with `green` true and `auditor` `green`; `tickets/invariant-auditor/checks.json` validates as the Check lane's `Invoice` with `passed` true; the test reads files from the checkout and writes nothing. The closed member list: `shakeout-tickets.bad_schema`; `shakeout-stages.scope_escape`, `premise_false`, `branch_only_red`, `base_red_excused`, `empty_diff`, `review_reject`, `reject_reentry_criteria_position`, `timeout_dead_ends`, `secret_not_persisted`; `shakeout-driver.schema_invalid_exhausts_reprompt`, `stuck_budget_killed`; `shakeout-reconcile.engine_death_reaped`; `shakeout-merge.conflicted_rebase_aborted`; `shakeout-providers.auth_expiry_classified`; `shakeout-drain.red_then_green_one_invocation`, `premise_park_released_by_edit`; `shakeout-ladder.identical_terminals_climb`, `identical_terminals_reject_when_exhausted`. A read that fails is answered `premise_failed` naming the unmet criterion and the artifact, and no seed is authored. (2) The Phase 3 CORE batch, authored DIRECTLY as `tickets/<stem>/ticket.md` files in the worktree (uncommitted, never on this branch): the seeds the section 19 Phase 3 bullet's Seeding partition names as its core batch, plus ONE `phase3-continue` seeding ticket carrying the batched contract for the remainder -- at most `seeding.max_seeds_per_admission` files in total; each seed `source: seed`, `state: confirmed`, `Depends on` including `phase2-exit`, a `## Plan contract` citing the sections that own its machinery, `Context` of existing paths only, a fence closed over every file its criteria force and over the module that owns each hooked seam, `Time budget` stuck at or under `drain.max_ticket_minutes`, `medium`/`medium` unless the plan names it known-hard, and a `-continue` seed whose fence is the tickets plane plus its own test file; a KNOWN-DEEP core seed rides an admission alone, chained by `depends`. If the Phase 3 bullet carries no Seeding partition at the Phase 4 bullet's depth (a CORE batch naming its stems and owning modules, and the `-continue` tail), answer `premise_failed` naming the thin Phase 3 bullet as the plan defect (SPEC DEPTH BEFORE SEEDING) and author nothing. (3) The batch's own test `tests/test_seeded_phase3_core.py` in the idiom of `tests/test_seeded_phase2.py`: it NAMES its batch's stems, asserts each lints, each `depends` edge, `source: seed`, the authored tier values, stuck under the envelope, the fence read closure against a pinned existing-file set, and the exit edge on `phase2-exit`; it pins identity and structure only -- never prose bytes, phrase substrings, criteria counts, dispatchability, or a terminal event -- and accepts a later `rejected` stamp. The run record's `## Predicted vs actual` names the seeds authored. A re-run of this stem treats its own previously lifted seeds as already-emitted output (the seed path's re-run exemption).

## Scope out
No edit to `SQUATCH_PLAN.md` (outside the fence; a thin bullet parks this ticket for the operator's plan commit). No Phase 3 FEATURE seed beyond the core batch and its `-continue` tail, no Phase 4+ seed (D10). No Suggestion Box message for any seed. No live-journal read, no journal window (no `Exit-read window` section: every read is a committed artifact). No hand-written report, no copy of `shakeout-report.json`, no new lift path. No change to any production module or spec; the only code-lane diff is the two test files.

## Scope fence
- tickets/
- tests/test_phase2_exit.py
- tests/test_seeded_phase3_core.py

## Acceptance criteria
- In `tests/test_phase2_exit.py`, `tickets/shakeout-ladder/shakeout-report.json` validates as `ShakeoutReport`, its `groups` are the eight battery groups in chain order, and every member of the closed list in Scope in is present with `green` true and `auditor` `green`.
- In `tests/test_phase2_exit.py`, `tickets/invariant-auditor/checks.json` validates as the Check lane's invoice with `passed` true.
- In `tests/test_seeded_phase3_core.py`, every authored Phase 3 core seed is named explicitly, lints, carries `source: seed`, `state: confirmed`, a `Depends on` edge on `phase2-exit`, a stuck budget at or under the configured `drain.max_ticket_minutes`, and the batch counts at most the configured `seeding.max_seeds_per_admission` files including `phase3-continue`.
- `uv run python -m eval.shakeout check tickets/shakeout-ladder/shakeout-report.json` exits 0.
- `git diff --name-only main...phase2-exit` lists exactly `tests/test_phase2_exit.py` and `tests/test_seeded_phase3_core.py`, and no path under `tickets/`.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_phase2_exit.py tests/test_seeded_phase3_core.py -q
uv run python -m eval.shakeout check tickets/shakeout-ladder/shakeout-report.json
git diff --name-only main...phase2-exit
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` naming the criterion and artifact if any exit read above fails against the committed artifacts, naming the thin Phase 3 bullet if section 19's Phase 3 bullet carries no Seeding partition (CORE batch with owning modules, plus the `-continue` tail) at the Phase 4 bullet's depth, if the core batch cannot be authored within `seeding.max_seeds_per_admission` files, if any file outside the fence must change, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 90m
- stuck: 180m
