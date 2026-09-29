---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- bug-gate-grammar
- report-inbox-triage

## Context
- squatch/scorecard.py
- tests/test_scorecard.py

## Plan contract
- section 20

## Goal
Attribute escaped bugs to the checks that admitted their merged change.

## Why
The fixture's machine-introduced escape needs a closed, history-backed scorecard column.

## Scope in
Source is resolved `bug_report` evidence `app_commit`, a lowercase SHA or `BASE..HEAD`. Git accepts only first-parent `HEAD` ancestry with one valid trailer pair (`squatch-ticket`, `squatch-reviewed-sha`); otherwise the evidence is unattributed. Status and Retro pass immutable `(signature,ticket)` into `RetroWindow`; scorecard remains pure. Count each passed-Check report/ticket/surface once, and exclude duplicate/fail/bypass/absent/unattributed data. `tests/test_mergequeue.py` changes only the public-Git allowlist for this operation. `squatch/git.py`, `squatch/retro.py`, `squatch/__main__.py`, `tests/test_git.py`, `tests/test_retro.py`, `tests/test_cli.py`, and `tests/test_mergequeue.py` are measured on-demand inspection exceptions.

## Scope out
Do not attribute foreign history, count a non-passing or duplicate observation, or add a second scorecard projection path.

## Scope fence
- squatch/scorecard.py
- squatch/git.py
- squatch/retro.py
- squatch/__main__.py
- tests/test_scorecard.py
- tests/test_git.py
- tests/test_retro.py
- tests/test_cli.py
- tests/test_mergequeue.py

## Acceptance criteria
- `tests/test_git.py` proves the public Git operation accepts only first-parent HEAD ancestry with exactly one valid `squatch-ticket` and `squatch-reviewed-sha` trailer pair.
- `tests/test_scorecard.py` proves each passed Check report/ticket/surface is counted once and excludes duplicate, fail, bypass, absent, unattributed, and foreign-history data.
- `tests/test_retro.py` and `tests/test_cli.py` prove Status and Retro pass immutable `(signature, ticket)` attribution into `RetroWindow` without making the scorecard impure.
- `tests/test_mergequeue.py` changes only the public-Git allowlist for this operation.

## Verification
```
uv run pytest tests/test_scorecard.py tests/test_git.py tests/test_retro.py tests/test_cli.py tests/test_mergequeue.py -q
uv run pytest -q
```

## Definition of rejected
Reject an unproven trailer, non-first-parent ancestry, impure projection, duplicate escape, or an edit outside the fence.

## Time budget
- expected: 75m
- stuck: 150m
