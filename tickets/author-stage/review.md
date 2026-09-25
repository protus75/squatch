---
verdict: snag
reviewed_sha: 8e8fb4f0ebb4bd4f35bb119be852672f3adfe57a
produced_by_spec_version: '1.0'
produced_at_sha: 8e8fb4f0ebb4bd4f35bb119be852672f3adfe57a
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
Every acceptance criterion is met, every changed path is inside the fence, and the checks are green. One failure path is unhandled: after a successful LLM call, `Author.run` writes the ticket file to disk, then computes the starting state and commits with no handling. Any exception at that point strands an uncommitted ticket file and aborts the whole triage pass.

## Findings
- correctness_review at squatch/author.py:118: `Author.run` writes `tickets/<stem>/ticket.md` through `self._fs.write` before it calls `starting_state(...)` and `Intake.commit(...)`, and it catches no exception from either. Those calls can raise: `starting_state` raises ValueError for a `bug_report` message whose `origin` is not `self_diagnosed` or `player` (the Box accepts that class with any origin, and `bug_origin` falls back to None), and `Intake.commit` can raise a lint error or GitError. When one does, the exception escapes `Triage.run`, so this item and the rest of the pass are never processed and the `triage_pass` signal is never journaled. The uncommitted ticket file stays in the working tree: `pending_stems` then lists it as front-door work, so a later human `intake` would commit it as `source: human`, and `TicketSchemaGate` refuses that stem forever as 'already exists'. This is uncertain in one respect: nothing in the engine enqueues `bug_report` today, so the policy crash is latent, but a commit-lane failure after the write is not. The ticket requires that a failed authoring leave the message `pending` and that the pass continue. (paved road: Compute `parsed` and `state` from `authored.ticket` BEFORE any write to disk. Wrap the write and `Intake.commit` so that any failure removes the written `tickets/<stem>/` path through the filesystem seam, reports the reason, and returns None, leaving the message `pending` with its verdict. Add a test in which `Intake.commit` (or `starting_state`) raises: assert no ticket dir remains, the message stays `pending`, and the triage pass still journals its signal.)
