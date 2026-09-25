---
state: confirmed
source: seed
priority: P1
kind: feature
# section 19 pre-ladder tier rule: every code-bearing Phase 2 seed runs at the
# HIGH tier until the escalation ladder merges; effort stays at the default.
agent_tier: high
agent_effort: medium
---
## Depends on
- spine-caps

## Context
- squatch/runner.py
- squatch/stages.py
- squatch/merge.py
- squatch/reconcile.py
- squatch/git.py
- squatch/driver.py
- squatch/effects.py
- squatch/artifacts.py
- tests/test_terminal.py
- tests/test_reconcile.py
- tests/test_cli.py

## Plan contract
- section 11
- section 10
- section 6
- section 9

## Goal
Every non-ok terminal auto-harvests before its worktree is wiped: a fail-closed allowlist extraction lands in `tickets/<stem>/attempts/<n>/` through the one ticket-plane lift path, the terminal handler runs harvest -> journal -> wipe, reconcile-on-entry harvests an orphan before reaping it, and the next attempt's prior-attempts render carries the harvested material.

## Why
Section 11.2: the material only the dying worktree holds (the run record, the diff shape, the spool tails) is what the diagnosis call reads and what a findings-fed re-entry needs; today a non-ok run leaves its worktree in place and names the engine log as its detail. The Phase 1 re-entry render already folds the durable `review.md` and `checks.json` into the prior-attempts block; harvest EXTENDS that one rendered section with the worktree-only material -- one rendering seam, never a second path. The handler order is fixed and load-bearing: harvest precedes the terminal write (the diagnosis call of the next seed batch slots between them and reads the harvest), and no worktree is wiped until its terminal is journaled. Harvest is an allowlist because "everything except the diff" admits whatever nobody thought of, and the unreviewed diff never enters the ticket spec. Harvest is soft: a failed extraction must never cost the stem its terminal or its wipe.

## Scope in
A new module `squatch/harvest.py` owning the allowlist extraction as a pydantic `Artifact` model (`Harvest`) and its writer: the closed contents of `tickets/<stem>/attempts/<n>/` are `harvest.json` (outcome; the terminal stage's name; the terminal reason when the outcome carries no findings; the structured findings; cost -- usd, tokens, provider, model; wall seconds measured through the clock seam; `run_seq`; the `git diff --stat` of the worktree against the run's base -- names and counts, never content -- with uncommitted changes included; and a capped tail, `TAIL_CHARS` characters, of every file in the attempt's spool dir `<state_dir>/spools/<stem>/<n>/`, keyed by file name) plus `run.md` copied from the worktree outbox when the implementer wrote one. `<n>` IS the run sequence. `squatch/git.py` gains the one argv wrapper the stat needs. The stage-dispatch seam (`Pipeline.run` in `squatch/merge.py`, the `Pipeline` protocol in `squatch/runner.py`) returns the run's terminal as one object -- the stage layer's `Delivery`, extended with the terminal reason, the terminal stage's name, and the run's cost -- instead of a bare outcome string; every caller and every test fake follows in the same change. `squatch/runner.py`'s terminal handler for every non-ok outcome runs, in order: harvest (written into the canonical ticket dir and committed through the ONE lift path in `squatch/stages.py`, as its own ticket-plane commit kind), then the infra draw of `spine-caps` where it applies, then the terminal `state_transition` whose body carries `harvest`: the attempt dir's repo-relative path, or `null` when the setup-death short-circuit skipped it, and `harvest_error` naming the failure when the extraction raised (the traceback goes to the engine log; the terminal still journals), then the worktree wipe (`worktree_remove` + `worktree_prune` through `squatch/git.py`; the branch survives). Setup-death short-circuit: no worktree on disk means no harvest. The stop report names `tickets/<stem>/attempts/<n>/` as where the detail lives. `squatch/reconcile.py` harvests a present orphan worktree (outcome `abandoned`, the reason naming the reap, the base read from the run's workspace effect completion) BEFORE journaling `abandoned` and wiping it. `Stages._prior_attempts` in `squatch/stages.py` extends its rendered block: one line per earlier attempt's `harvest.json` (attempt, outcome, reason, files changed), plus the latest attempt's run record and spool tails, the whole harvest contribution capped at `HARVEST_RENDER_CHARS`, in the same attempt-scoped, untrusted position -- `ticket.md` is never written. Tests for every rule above. `tests/test_drain_reentry.py` is the re-entry render's existing test file and the idiom the new render claims extend, but it carries the engine's data-block delimiter and so cannot be a `Context` file (section 8's render contract refuses it): read it in the worktree before extending it.

## Scope out
No diagnosis call, no `lessons`, no ladder, no Reject queue, no Suggestion Box: harvest enqueues second problems only once the box exists (a later seed), and the raw-versus-lessons render swap lands with the diagnosis call. No tee of the agent CLI's raw stdout, stderr, or event stream into the attempt spool: that section 6 gap is filed separately; harvest cuts tails from whatever the attempt spool dir holds, so the tee lands later with no harvest change. No wipe of the branch, no change to teardown-and-create at the next run, no change to the merge admission's own retire path, no change to `ticket.md`, no new frontmatter field, no new config key, no new journal event type, no change to `specs/`. No content of the diff in any harvested file. No change to any existing test's claim beyond the seam's new return shape and the Phase 1 "worktree left in place" pins, which this ticket replaces with the wipe.

## Scope fence
- squatch/harvest.py
- squatch/runner.py
- squatch/stages.py
- squatch/merge.py
- squatch/reconcile.py
- squatch/git.py
- tests/

## Acceptance criteria
- In `tests/test_harvest.py`, a run ending `gate_failed` over a worktree carrying an uncommitted `tickets/<stem>/run.md` and one changed source file leaves `tickets/<stem>/attempts/0/harvest.json` and `tickets/<stem>/attempts/0/run.md` committed on main, `harvest.json` validating as the `Harvest` model with the run's outcome, findings, `run_seq` 0, a `diff --stat` naming the changed file, and a spool tail keyed by every file the attempt's spool dir holds.
- In `tests/test_harvest.py`, no harvested file carries a line of the changed source file's content, and every spool tail is at most `TAIL_CHARS` characters.
- In `tests/test_terminal.py`, for a non-ok run the journal order is: the harvest lift's ticket-plane commit, then the run's terminal `state_transition` whose body's `harvest` names `tickets/<stem>/attempts/<n>`, and after `Runner.dispatch` returns the worktree directory is gone while the branch still exists.
- In `tests/test_terminal.py`, a run whose workspace never materialized journals its terminal with `harvest` null and no `attempts/` dir, and a harvest whose extraction raises still journals the terminal (body `harvest_error` set) and still wipes the worktree.
- In `tests/test_terminal.py`, the stop report line for a non-ok run names `tickets/<stem>/attempts/<n>/` as the detail location.
- In `tests/test_reconcile.py`, an orphan left `running` with a worktree holding an uncommitted `run.md` is harvested to `tickets/<stem>/attempts/<n>/` before its `abandoned` terminal is journaled and its worktree removed.
- In `tests/test_drain_reentry.py`, the second attempt's Implement prompt carries, inside the `prior_attempts` block and nowhere else, the prior attempt's harvested outcome, reason, and `diff --stat` line, the prior-attempts block stays under `HARVEST_RENDER_CHARS` plus its Phase 1 content, and the first attempt still renders no `prior_attempts` block.
- In `tests/test_cli.py`, `FakePipeline` returns the seam's terminal object and every Phase 1 drain, reconcile, and CLI claim still passes under it.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_harvest.py -q
uv run pytest tests/test_terminal.py tests/test_reconcile.py tests/test_drain_reentry.py tests/test_cli.py tests/test_git.py -q
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` if the harvest cannot reach main through the existing lift path in `squatch/stages.py` without a second ticket-plane writer, if the seam's return object cannot carry the terminal reason and cost without a change to `specs/` or to `ticket.md`, if any file outside the fence must change, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 90m
- stuck: 180m
