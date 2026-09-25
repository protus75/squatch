---
verdict: snag
reviewed_sha: 47b0ff56ceb42c50e12e717197e0c1245fc3e028
produced_by_spec_version: '1.0'
produced_at_sha: 47b0ff56ceb42c50e12e717197e0c1245fc3e028
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The seed path is built and every acceptance test is present and green. Two defects remain: the shared ticket-plane lane now journals a false intake signal for every caller, and a lift that fails partway leaves the seeding stem unable to re-run.

## Findings
- correctness_review at squatch/tickets.py:790: `commit_lane` is the one lane for every caller: human `run` intake, machine authoring, and reject stamps. Before this change, re-committing unchanged bytes failed at `git commit`. Now, if the path is clean, it skips the commit and journals a `ticket_intake` signal whose `commit` is the current `HEAD`, which is not the commit that wrote those bytes. So any re-intake of an unchanged ticket, not only a seed re-offer, restarts the age term and records a false authoring commit in the journal. That journal is permanent. (paved road: Keep the clean-path fallback only where it is needed: effect replay of the seed lift. Either `_lift_seeds` skips `Intake.commit` for a seed whose bytes on main already equal `seed.sha`, or the fallback records the commit that last touched the path (a `git.py` log wrapper for that path), never `HEAD`. Leave non-seed callers failing as before, and add a test for a clean re-intake through the human lane.)
- correctness_review at squatch/stages.py:870: I'm not certain this is reachable in practice, but if it is, the stem is stuck. `_lift_seeds` writes every seed to the canonical checkout, then commits them one at a time, and journals the `seed_lift` signal only after all of them succeed. If any `Intake.commit` raises partway (the second lint fails, or the byte-mismatch `ValueError`), one or more seeds are already committed on main with no `seed_lift` signal. On the next run, `validate_batch` treats those stems as foreign collisions, because `_prior_lifted` only reads `seed_lift` signals. The seeder can never re-offer its own seeds, and nothing releases the hold. Uncommitted seed files are also left in the canonical working tree. (paved road: Make the lift all-or-nothing from the RE-RUN rule's point of view. Either run every lint and byte check before the first commit so nothing that can fail runs after one, or let the collision check also exempt stems whose `ticket_intake` signal came from this seeder's lift effect. Add a test where the second seed's intake fails and the re-offer still succeeds.)
