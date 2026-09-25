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
- diagnosis-eval-harness

## Context
- config.yaml
- eval/harness.py

## Plan contract
- section 11
- section 6

## Goal
The merged diagnosis eval has been executed once against the routed real model and its report rests on main at `eval/reports/diagnosis-eval.json`, agreement rate recorded, produced by the already-merged harness with no code, spec, or fixture change.

## Why
Section 19: the spend ticket only EXECUTES the harness the previous seed merged and reviewed, budget-capped by the harness's flat per-run USD constant, so the first paid diagnosis calls run reviewed code and leave a committed record of how well the `diagnose` surface agrees with the fixture set. The report is the diff: a run that produced nothing has no evidence to merge, and the verification gate refuses an empty committed diff (section 11.1), so the report reaches main on the code lane at a fixed path the next batch's ladder seed and the operator can read.

## Scope in
From the worktree root, run `uv run python -m eval.diagnose --report eval/reports/diagnosis-eval.json` until the written report's `stopped` is null: each invocation is capped at `USD_CAP` and replays the fixtures an earlier invocation completed at no cost, so a budget stop is continued by the same command, never by an edit. Commit exactly that one file on the branch. The run record's `## Predicted vs actual` states the agreement rate predicted before the run and the rate the report recorded; its `## Resolved engine/model` names the report's `identity`. A harness refusal (a placeholder routing row, a fixture author identical to the diagnose identity, a missing spec) is a config or plan defect, not something to fix here.

## Scope out
No change to `eval/diagnose.py`, `eval/diagnose_fixtures/`, `squatch/`, `specs/`, `config.yaml`, or any test; no second report path; no re-authoring of a fixture the model disagreed with; no interpretation of the rate beyond recording it -- what the ladder does with the surface is the next batch's judgment.

## Scope fence
- eval/reports/

## Acceptance criteria
- `eval/reports/diagnosis-eval.json` exists on the branch and `uv run python -m eval.diagnose --check eval/reports/diagnosis-eval.json` exits 0.
- `eval/reports/diagnosis-eval.json` carries `stopped` null, `summary.scored` equal to the committed fixture count, a numeric `summary.agreement_rate`, and an `identity` whose provider and model are the ones `config.yaml` routes to `diagnose` (or, with no `diagnose` row, to `review`) at the exercised tier.
- `git diff --name-only main...diagnosis-eval-run` lists exactly `eval/reports/diagnosis-eval.json`.
- `uv run pytest -q` exits 0.

## Verification
```
uv run python -m eval.diagnose --check eval/reports/diagnosis-eval.json
git diff --name-only main...diagnosis-eval-run
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` if the harness refuses to run before any call, if three capped invocations do not complete the fixture set, or if completing the run needs any edit outside `eval/reports/`.

## Time budget
- expected: 45m
- stuck: 90m
