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
- shakeout-reconcile

## Context
- squatch/merge.py
- squatch/git.py
- squatch/runner.py
- tests/test_merge.py
- tests/test_git.py

## Plan contract
- section 19
- section 9
- section 10
- section 11

## Goal
The merge shakeout group pins `squatch/merge.py`: a conflicted rebase is refused, aborted, and leaves no half-rebased worktree, the stem terminals `gate_failed` drawing retry and stays re-runnable on its own branch head -- re-confirming every prior group's entries before appending its own.

## Why
Section 19 names the member "a conflicted rebase leaves no half-rebased worktree", and sections 9-11 fix its owner and shape: admission is the merge queue's, a refused rebase runs `rebase --abort` before it returns (section 10), and pre-Rework the refusal is a `gate_failed` drawing retry (section 11.1). The discriminating observable is the worktree's git state after the refusal: no `rebase-merge` or `rebase-apply` directory, HEAD at the branch's own head, the terminal `gate_failed` with a `post_rebase_regate` finding -- a faked refusal that skips the abort cannot leave the tree in that state.

## Scope in
A new member module `eval/shakeout/merge_group.py` with `GROUP` = `shakeout-merge` and `MEMBERS`: `conflicted_rebase_aborted` -- the bench commits a change to a file on main after the run's worktree branched and the fake implementer commits a conflicting change to the same lines; observable: the terminal `gate_failed` carrying a `post_rebase_regate` finding with the rebase road, the worktree carrying no rebase-in-progress state, its HEAD equal to the branch's own head, and main's tree hash unchanged; expected `gate_failed:rebase_aborted`; detail `tickets/<stem>/attempts/<n>/harvest.json`. `eval/shakeout/registry.py`'s `GROUPS` gains `("shakeout-merge", "eval.shakeout.merge_group")` after the reconcile group. `tests/test_merge.py` gains the unit pin on the worktree's post-refusal state where the existing tests carry none. The report is produced by this ticket's own `## Verification` with `--prior tickets/shakeout-reconcile/shakeout-report.json`.

## Scope out
No change to `squatch/merge.py` or any production module. No resolution rungs, no Rework, no per-path strategies (Phase 3). No hand-written entry, no edit of a prior group's entries.

## Scope fence
- eval/shakeout/merge_group.py
- eval/shakeout/registry.py
- tests/test_merge.py

## Acceptance criteria
- In `tests/test_merge.py`, after a refused conflicted rebase the worktree holds no rebase-in-progress state, its HEAD equals the branch head, and main's tree hash is unchanged.
- `uv run python -m eval.shakeout run --outbox tickets/shakeout-merge --prior tickets/shakeout-reconcile/shakeout-report.json` exits 0 and writes `tickets/shakeout-merge/shakeout-report.json` whose prior entries are byte-identical to the reconcile group's report and whose new entry is `shakeout-merge.conflicted_rebase_aborted`, `green` true and `auditor` `green`.
- `uv run python -m eval.shakeout check tickets/shakeout-merge/shakeout-report.json` exits 0.
- `git diff --name-only main...shakeout-merge` lists `eval/shakeout/merge_group.py`, `eval/shakeout/registry.py`, and `tests/test_merge.py`, and no path under `tickets/`.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_merge.py tests/test_shakeout.py -q
uv run python -m eval.shakeout run --outbox tickets/shakeout-merge --prior tickets/shakeout-reconcile/shakeout-report.json
uv run python -m eval.shakeout check tickets/shakeout-merge/shakeout-report.json
git diff --name-only main...shakeout-merge
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` naming the member if the merged engine does not produce the stated observable, if the bench as landed cannot advance main under a live worktree, if a prior group's committed entry cannot be re-confirmed byte-for-byte, if any file outside the fence must change, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 45m
- stuck: 90m
