---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: high
agent_effort: high
---
## Depends on
- phase3-continue-22

## Context
- squatch/stages.py

## Plan contract
- section 20

## Goal
Admit a no-code ticket whose schema-validated deliverable was lifted from its OUTBOX.

## Why
The ordinary lane lifts and validates `soak-run`'s uncommitted report before Check, but Verification rejects its intentionally empty committed code diff. Committing the report instead is correctly refused because `tickets/**` never rides the code lane.

## Scope in
Recognize durable output evidence from the same run at initial Check and merge regate. A completed run-scoped lift qualifies only when its result names at least one path under `tickets/<stem>/` whose basename is registered in `KNOWN_ARTIFACTS`, excluding `run.md`, and the branch has no committed diff. Use that evidence to permit the otherwise-empty implemented diff at both Verification passes. Preserve the existing empty-diff rejection when the lift is absent, belongs to another run/stem, contains only engine records, or names an unknown artifact.

Keep committed `tickets/**` refused by code-lane safety. Never exempt an uncommitted edit outside the ticket's own OUTBOX. On successful empty-code admission, preserve `commit: null`, retire the branch/worktree, and journal one `merged` transition while the lifted ticket-plane artifact remains the deliverable.

The exact embedded Context is `squatch/stages.py`. `squatch/merge.py`, `tests/test_stages.py`, and `tests/test_merge.py` are fenced on-demand inspection exceptions because embedding these large production and test surfaces breaches `REQ_RENDER_HEADROOM`.

## Scope out
Do not weaken artifact schema validation, scope fencing, Verification commands, review, code-lane safety, unknown-artifact handling, or ordinary empty-diff rejection. Do not special-case `soak-run` or the daemon report filename.

## Scope fence
- squatch/stages.py
- squatch/merge.py
- tests/test_stages.py
- tests/test_merge.py

## Acceptance criteria
- `tests/test_stages.py` proves a same-stem/run completed lift naming a registered non-run-record artifact permits an otherwise-empty implemented diff, while missing, stale, foreign, run-record-only, and unknown-artifact lifts do not.
- `tests/test_merge.py` proves merge regate replays the same qualification, keeps `commit: null`, retires once, and journals one merged transition without a code-lane commit.
- `tests/test_merge.py` preserves refusal of committed `tickets/**`, and `tests/test_stages.py` preserves rejection of ordinary empty diffs and uncommitted code edits.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_stages.py tests/test_merge.py -q
uv run pytest -q
```

## Definition of rejected
Reject a stem/name special case, unknown output, cross-run evidence, committed ticket output, uncommitted code exemption, synthetic signal not backed by a completed lift, duplicate terminal, or non-null code commit.

## Time budget
- expected: 90m
- stuck: 180m
