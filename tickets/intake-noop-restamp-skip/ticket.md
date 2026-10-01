---
priority: P2
kind: bug
agent_tier: medium
agent_effort: medium
source: box:suggestion
state: draft
---
## Depends on
- none

## Context
- squatch/tickets.py
- squatch/git.py
- tests/test_tickets.py

## Goal
`Intake.run` in `squatch/tickets.py` stops treating a byte-identical restamp as a crash. When a pending stem's stamped text comes back identical to that stem's blob already committed at HEAD, `Intake.run` leaves the on-disk bytes as stamped, makes no commit, journals no new intake signal, lists the stem in neither `IntakeResult.committed` nor `IntakeResult.refused`, and continues the pass so every other pending ticket in that pass still commits.

## Why
`pending_stems` treats any working-tree difference from HEAD as pending, so an operator who strips a committed ticket's `source`/`state` lines makes that ticket pending again; `stamp` puts the same lines back in the same place, so the pathspec `git commit` in `commit_lane` has nothing new to commit and `Git.commit` raises a raw `GitError`. `Intake.run` catches only `TicketLintError`, so that one no-op stem aborts the whole intake pass and strands every other pending ticket uncommitted for that cycle. The fix compares the stamped text against HEAD's committed blob before the commit is attempted, deciding a clean skip instead of reacting to the commit failure.

## Scope in
The path inside `squatch/tickets.py` between stamping a pending ticket and calling `commit_lane` (`Intake.run` and/or `Intake.commit`) detects that the stamped text's git blob hash equals the HEAD blob hash already resolved for that stem's path (via `Git.rev_parse(repo, f"HEAD:{rel}")`, treating a `GitError` from an unresolvable HEAD path as "not identical"), and when so, skips the commit and journal signal for that stem and moves on, instead of calling `commit_lane` and letting the resulting `GitError` propagate.

## Scope out
`pending_stems`'s definition of a pending stem (any working-tree diff from HEAD) does not change. `stamp`'s field-replacement behavior does not change. A stem whose stamped text is NOT byte-identical to HEAD keeps committing and journaling exactly as today. No other `commit_lane` caller's error handling changes.

## Scope fence
- squatch/tickets.py
- tests/test_tickets.py

## Acceptance criteria
- Calling `Intake.run` on a repo holding one committed ticket rewritten on disk with its `source`/`state` lines removed, plus a second, valid pending ticket, raises no exception, proved by `tests/test_tickets.py::test_restamping_a_committed_ticket_to_its_head_bytes_skips_cleanly`.
- After that call, the rewritten stem's `ticket.md` bytes on disk equal its HEAD blob again, proved by `tests/test_tickets.py::test_restamping_a_committed_ticket_to_its_head_bytes_skips_cleanly`.
- After that call, HEAD holds exactly one new commit beyond the fixture's starting point, the second ticket's, proved by `tests/test_tickets.py::test_restamping_a_committed_ticket_to_its_head_bytes_skips_cleanly`.
- After that call, the journal holds exactly one new `signal` event and it is the second ticket's intake signal, proved by `tests/test_tickets.py::test_restamping_a_committed_ticket_to_its_head_bytes_skips_cleanly`.
- The rewritten stem appears in neither `IntakeResult.committed` nor `IntakeResult.refused`, proved by `tests/test_tickets.py::test_restamping_a_committed_ticket_to_its_head_bytes_skips_cleanly`.
- The full ticket test module still passes, checked by `uv run pytest tests/test_tickets.py -q`.

## Verification
```
uv run pytest tests/test_tickets.py::test_restamping_a_committed_ticket_to_its_head_bytes_skips_cleanly -q
uv run pytest tests/test_tickets.py -q
```

## Regression
```
uv run pytest tests/test_tickets.py::test_restamping_a_committed_ticket_to_its_head_bytes_skips_cleanly -q
```
- carries: tests/test_tickets.py

## Definition of rejected
Throw the branch away if closing this cleanly would require loosening what `pending_stems` or `stamp` consider pending, adding a second commit path around `commit_lane` that its other callers do not share, or catching `GitError` by matching its message text instead of deciding before the commit is attempted.

## Time budget
- expected: 30m
- stuck: 60m
