---
priority: P3
kind: chore
agent_tier: medium
agent_effort: medium
source: box:suggestion
state: draft
---
## Depends on
- none

## Context

## Plan contract
- section 10
- section 11
- section 13

## Goal
`SQUATCH_PLAN.md` names the on-disk `tickets/<stem>/diagnosis.json` artifact in the three places that already describe or imply it without naming it: section 11.3's diagnosis-verdict item states the verdict's `lessons` are persisted there through the one ticket-plane lift path, in addition to being journaled on the run's terminal `state_transition`; section 10's ticket-plane commit artifact list names it beside `checks.json`, review verdicts, and harvest `attempts/` dirs; and section 13's per-ticket directory layout names it beside `ticket.md`, `run.md`, `review.md`, `checks.json`, and `attempts/<n>/`. The section 0 operator-recovery passage that already names `diagnosis.json` is left unchanged and now points at a specified artifact.

## Why
The merged spine-diagnosis stage writes `tickets/<stem>/diagnosis.json`, the operator-recovery order already tells operators to read it, and the open `drain-parked-detail` ticket already points at it as a per-ticket artifact. But section 11.3 says only that `lessons` is journaled, and neither section 10's commit-artifact list nor section 13's per-ticket layout names the file. Because the plan is the seed, regenerating the diagnosis machinery from the plan as written could drop the file without breaking anything the plan states, silently breaking the recovery order and the parked-report pointer that depend on it existing on disk.

## Scope in
Edit `SQUATCH_PLAN.md` only, in three places:
- Section 11.3's diagnosis-verdict sentence ("The verdict includes a `lessons` field, journaled and rendered as the harvest's form in every later attempt's prior-attempts section"): state that the verdict and its `lessons` are also persisted to `tickets/<stem>/diagnosis.json` through the one ticket-plane lift path (section 10), alongside being journaled on the terminal `state_transition`.
- Section 10's ticket-plane commit artifact list (the "TICKET-PLANE COMMITS" sentence naming authored tickets, run records, `checks.json`, review verdicts, harvest `attempts/` dirs, evidence copies, decision records, retro reports): add `diagnosis.json` to that list.
- Section 13's `Layout: **one directory per ticket**` sentence (naming `ticket.md`, `run.md`, `review.md`, `checks.json`, `attempts/<n>/`, evidence): add `diagnosis.json` to that list.

## Scope out
Do not change diagnosis behavior, code, specs, or tests. Do not touch the section 0 operator-recovery passage, which already names `diagnosis.json` correctly. Do not rename or relocate the artifact, and do not add new sections or worked examples beyond naming the existing fact in these three places.

## Scope fence
- SQUATCH_PLAN.md

## Acceptance criteria
- Section 11.3 states that the diagnosis verdict's `lessons` are persisted to `tickets/<stem>/diagnosis.json`, in addition to being journaled on the run's terminal `state_transition` (checked by `grep -n "persisted to tickets/<stem>/diagnosis.json" SQUATCH_PLAN.md`).
- Section 10's ticket-plane commit artifact list names `diagnosis.json` beside `checks.json`, review verdicts, and harvest `attempts/` dirs (checked by `grep -n "diagnosis.json" SQUATCH_PLAN.md` showing a match on that list's line).
- Section 13's per-ticket directory layout names `diagnosis.json` beside `ticket.md`, `run.md`, `review.md`, `checks.json`, and `attempts/<n>/` (checked by `grep -n "diagnosis.json" SQUATCH_PLAN.md` showing a match on the "Layout: one directory per ticket" line).
- `SQUATCH_PLAN.md` gains exactly three new occurrences of `diagnosis.json` beside the one already present, and no other tracked file changes (checked by `grep -c diagnosis.json SQUATCH_PLAN.md` reading 4, and by `git diff --name-only` naming only `SQUATCH_PLAN.md`).

## Verification
```
grep -c diagnosis.json SQUATCH_PLAN.md
grep -n "persisted to tickets/<stem>/diagnosis.json" SQUATCH_PLAN.md
grep -n "diagnosis.json" SQUATCH_PLAN.md
git diff --name-only
```

## Definition of rejected
Stop and throw the branch away if closing this gap turns out to require restating the diagnosis artifact's semantics (changing when or how it is written) rather than just naming an already-true fact in three places -- that is a behavior change, not a documentation gap, and belongs in a separate ticket.

## Time budget
- expected: 20m
- stuck: 60m
