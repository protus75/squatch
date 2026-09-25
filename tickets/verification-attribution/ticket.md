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
- suggestion-box

## Context
- squatch/stages.py
- squatch/git.py
- squatch/seams.py
- squatch/gates.py
- squatch/artifacts.py
- squatch/config.py
- tests/test_git.py
- tests/test_terminal.py

## Plan contract
- section 7
- section 11
- section 12
- section 9

## Goal
The verification gate attributes every red `## Verification` command by BASE DIFF: a command red on the branch is re-run at the merge base, one also red there is a pre-existing base failure -- excused in `checks.json`, filed into the Suggestion Box as a `failure_report`, charged to neither the Check nor any cap -- while a command green at the base and red on the branch fails the Check exactly as before, per command and never per test.

## Why
Section 7 states the attribution and dates it: Phase 1 shipped the gate WITHOUT it (any red fails), and the attribution lands with the Phase 2 spine beside its filing consumer, the Suggestion Box -- which `suggestion-box` has now landed, so this seed follows it. A full-suite command must never fail a stem for a red it did not introduce; without attribution every inherited red is charged to the branch, drawing retry and diagnosis budget against a defect the stem cannot fix, which is the accretion section 11.1 bounds and section 11.7 routes: a pre-existing failure is verified on the base commit, then filed, never fixed inline. Attribution is per COMMAND because the engine ships no per-runner output parsing (section 18), and the merge-time INTEGRATION CHECK on a green main stays the backstop for any command the base excused. Section 9 puts the gate with its owner: the verification gate is the stage layer's, so `squatch/stages.py` owns the base run, and the one new git operation it needs lands in `squatch/git.py`.

## Scope in
`squatch/stages.py`: the `Verification` gate runs every command on the branch as landed; for each command red on the branch it creates ONE detached worktree of the merge base (`slip.base`) under `<worktree_root>/<stem>-base-<run_seq>/` through a new `Git.worktree_add_detached` argv wrapper in `squatch/git.py` (created once per check on the first red, removed with `worktree_remove` + `worktree_prune` before the gate returns, whatever the outcome -- never a bare delete), runs the SAME argv there with the same child environment and stuck timeout through the process seam, and classifies: red at the base too -- a PRE-EXISTING base red: no finding, one `failure_report` enqueued into the box built over the state dir and seams the stage layer holds (origin the stem, stage `check`, outcome `base_red`, reason the command line plus the redacted output tail, so the section 12 signature dedups the same base red across stems), the `CheckEntry` for that command recording `attribution: base` and `filed: <box id>` (additive fields on the closed model); green at the base -- the branch's own regression: the finding exactly as landed with `attribution: branch`; a command green on the branch records `attribution: null`. A base worktree that cannot be created, or a base run that itself raises, is fail-closed: the command's finding stands with `attribution: branch` and the reason. The empty-diff and `already_satisfied` rules of the gate are unchanged and never attributed. `build_invoice` carries the new entry fields into `checks.json`. Tests for every rule above; read `squatch/box.py` in the worktree (it lands with `suggestion-box` and did not exist when this seed was authored).

## Scope out
No per-test parsing, no runner-specific output reading, no quarantine ledger, no flake detection (section 11.5, Phase 3). No change to the merge admission's regate or integration check. No excusing of an empty diff. No change to the scope-fence, run-record, or diff-budget gates, to harvest, to `ticket.md`, or to any frontmatter field, config key, cap, or journal event type: the filed report is a box message, and the attribution rides `checks.json`.

## Scope fence
- squatch/stages.py
- squatch/git.py
- tests/test_stages.py
- tests/test_git.py
- tests/test_terminal.py

## Acceptance criteria
- In `tests/test_git.py`, `worktree_add_detached` creates a detached worktree at the named commit through the argv seam and `worktree_remove` plus `worktree_prune` leave no registry entry behind.
- In `tests/test_stages.py`, a `Verification` check over a branch whose one command is red on the branch and red at the merge base reports `pass`, its entry carries `attribution: base` and a `filed` id, and exactly one `failure_report` with `origin` the stem and `outcome` `base_red` is pending under `<state_dir>/box/`; a second stem inheriting the same base red collapses onto that message (`reports` 2).
- In `tests/test_stages.py`, a command green at the base and red on the branch reports `fail` with the finding as landed and `attribution: branch`; a command green on the branch carries `attribution` null; after either check no `<stem>-base-` worktree remains on disk or in `git worktree list`.
- In `tests/test_stages.py`, a base worktree whose creation is refused by the fake git leaves the branch finding standing with `attribution: branch`, and a branch with no committed diff still fails on the empty-diff finding with no base run made.
- In `tests/test_terminal.py`, a run whose only red command is a base red reaches Review with `tickets/<stem>/checks.json` committed carrying the excused entry, and journals no `cap_consumed` event.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_stages.py tests/test_git.py -q
uv run pytest tests/test_terminal.py -q
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` if the base run cannot be placed inside the `Verification` gate's `check` without a second gate or a second check effect, if `CheckEntry` as landed cannot carry two additive fields, if `squatch/box.py` as landed cannot be built from the stage layer's state dir and seams, if any file outside the fence must change, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 60m
- stuck: 120m
