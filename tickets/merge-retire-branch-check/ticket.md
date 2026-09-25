---
priority: P2
kind: bug
source: human
state: confirmed
---
## Depends on
- none

## Context
- squatch/merge.py
- squatch/git.py
- tests/test_merge.py

## Plan contract
- section 9
- section 10

## Goal
The merge admission's branch retirement re-raises a failed branch delete only while the branch still exists, and tolerates it only when the branch is already gone.

## Why
`Merge._retire` in `squatch/merge.py` catches a `GitError` from `branch_delete` and then calls `rev_parse refs/heads/<stem>` as its tolerance check. The comment says "re-raise if it exists", but `rev_parse` RAISES when the branch is already gone (the case meant to be tolerated) and returns silently when the branch still exists (the case meant to re-raise). The fallback is inverted. The intent: a branch already deleted is settled; a branch that survived a failed delete is a stuck retirement the operator must see, never a silent success.

## Scope in
Rewrite the fallback in `Merge._retire` so that after a failed `branch_delete`, the admission checks whether `refs/heads/<stem>` still resolves, re-raises the original `GitError` when it does, and returns normally when it does not. Add tests in `tests/test_merge.py` pinning both sides of that decision.

## Scope out
No change to `squatch/stages.py`, `squatch/git.py`, or any other module. No change to the retire effect key (`retire/<stem>/<run_seq>`), the worktree removal that precedes the delete, the squash, or the journal record. No new git operation in `git.py`; the check uses the existing `rev_parse`.

## Scope fence
- squatch/merge.py
- tests/test_merge.py

## Acceptance criteria
- In `squatch/merge.py`, a failed `branch_delete` whose branch is already gone lets `Merge._retire` return normally with `{"branch": <stem>}`, and `Merge.admit` settles `ok`.
- In `squatch/merge.py`, a failed `branch_delete` whose branch still exists re-raises the original `GitError` out of `Merge.admit`.
- `tests/test_merge.py` carries one test for each of the two cases above, each driven through a `Git` whose `branch_delete` raises `GitError`, and both test names contain the word `retire`.
- `python -m pytest tests/test_merge.py -q` exits 0.
- `python -m pytest -q` exits 0.

## Verification
```
python -m pytest tests/test_merge.py -q
python -m pytest -q
```

## Regression
```
python -m pytest tests/test_merge.py -q -k retire
```
- carries: tests/test_merge.py

## Definition of rejected
Stop and answer premise_failed if the fix needs a new operation in `squatch/git.py`, a change to `squatch/stages.py`, or any edit outside the two fenced paths, or if `tests/test_merge.py` is red on the base commit before any edit.

## Time budget
- expected: 20m
- stuck: 45m
