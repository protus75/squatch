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
- shakeout-driver

## Context
- squatch/reconcile.py
- squatch/runner.py
- squatch/drain.py
- tests/test_reconcile.py
- tests/test_drain.py

## Plan contract
- section 19

## Goal
The reconcile shakeout group pins `squatch/reconcile.py`: an engine death mid-call leaves a `running` with no terminal, the next entry reaps it `abandoned` after harvesting its worktree, and the stem re-enters findings-fed with a fresh run sequence -- re-confirming every prior group's entries before appending its own.

## Why
Section 19 names the live-failure member "engine death mid-call reaped/harvested/re-entered findings-fed", and section 11.2 fixes its owner and order: reconcile-on-entry reaps an orphaned in-flight run, harvesting before the `abandoned` terminal and the wipe, and section 6's run-scoped keys make the re-run real work under the next sequence. The discriminating observables are the `abandoned` terminal for run sequence `n` preceded by the harvest lift of `attempts/<n>/`, and the re-entry's `running` transition carrying `run_seq` `n + 1` with the prior attempt rendered into its prompt -- a faked reap cannot produce the harvest dir from a worktree it never held.

## Scope in
A new member module `eval/shakeout/reconcile_group.py` with `GROUP` = `shakeout-reconcile` and `MEMBERS`: `engine_death_reaped` -- the bench starts a run whose fake implementer writes `run.md` then raises a process-death fault the runner treats as a fault (no terminal written, the worktree left in place), then a second bench entry over the same state dir; observable: the second entry journals `attempts/<n>/` harvest lift then `to: abandoned` for run `n`, then a `running` with `run_seq` `n + 1` whose spooled Implement prompt carries the prior attempt's harvested outcome; expected `abandoned:harvested_reentered`; detail `tickets/<stem>/attempts/<n>/harvest.json`. `eval/shakeout/registry.py`'s `GROUPS` gains `("shakeout-reconcile", "eval.shakeout.reconcile_group")` after the driver group. `tests/test_reconcile.py` gains the unit pin for the re-entry sequence where the existing tests carry none. The report is produced by this ticket's own `## Verification` with `--prior tickets/shakeout-driver/shakeout-report.json`.

## Scope out
No change to `squatch/reconcile.py` or any production module. No daemon restart-reconcile, no orphan sweeper (Phase 3). No hand-written entry, no edit of a prior group's entries.

## Scope fence
- eval/shakeout/reconcile_group.py
- eval/shakeout/registry.py
- tests/test_reconcile.py

## Acceptance criteria
- In `tests/test_reconcile.py`, a reaped orphan's `abandoned` terminal carries its run sequence and the next dispatch of the stem takes the following sequence with the prior attempt rendered.
- `uv run python -m eval.shakeout run --outbox tickets/shakeout-reconcile --prior tickets/shakeout-driver/shakeout-report.json` exits 0 and writes `tickets/shakeout-reconcile/shakeout-report.json` whose prior entries are byte-identical to the driver group's report and whose new entry is `shakeout-reconcile.engine_death_reaped`, `green` true and `auditor` `green`.
- `uv run python -m eval.shakeout check tickets/shakeout-reconcile/shakeout-report.json` exits 0.
- `git diff --name-only main...shakeout-reconcile` lists `eval/shakeout/reconcile_group.py`, `eval/shakeout/registry.py`, and `tests/test_reconcile.py`, and no path under `tickets/`.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_reconcile.py tests/test_shakeout.py -q
uv run python -m eval.shakeout run --outbox tickets/shakeout-reconcile --prior tickets/shakeout-driver/shakeout-report.json
uv run python -m eval.shakeout check tickets/shakeout-reconcile/shakeout-report.json
git diff --name-only main...shakeout-reconcile
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` naming the member if the merged engine does not produce the stated observable, if the bench as landed cannot leave a `running` with no terminal and re-enter over the same state dir, if a prior group's committed entry cannot be re-confirmed byte-for-byte, if any file outside the fence must change, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 45m
- stuck: 90m
