---
verdict: snag
reviewed_sha: b4238ad7499c9306635c736242e0626db46ebeb3
produced_by_spec_version: '1.0'
produced_at_sha: b4238ad7499c9306635c736242e0626db46ebeb3
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The seed path is mostly sound: every changed file is inside the fence, and each acceptance criterion has a test. One defect remains: the extra interrupted-lift exemption in `_prior_lifted` can let a seeder overwrite another seeder's lifted stem, which breaks the rule that foreign stems stay protected.

## Findings
- correctness_review at squatch/seeds.py:151: `_prior_lifted` opens a window on this seeder's `lift/<seeder>/*/seeds` effect_intent. While the window is open, it adds every `ticket_intake` signal with `source: seed` to this seeder's exempt set, without checking which seeder produced the intake. The window only closes when this seeder's own lift effect completes. Failure case: seeder A's lift is interrupted after its intent, and A never reaches a completed lift again (for example, a later run fails at Check). Seeder B then lifts `b-seed`. That journals a `ticket_intake`/seed signal, which A's still-open window counts as A's own output. A later A run that authors `tickets/b-seed/ticket.md` passes `validate_batch` with no collision finding and overwrites B's seed through the lift. This violates the ticket's rule that only this seeder's own prior `seed_lift` exempts a stem, that foreign stems stay protected, and that no foreign existing stem is overwritten. The exemption also goes beyond the ticket's stated RE-RUN rule, which is keyed on a prior `seed_lift` signal of this seeder. (paved road: Attribute a partial lift to this seeder directly instead of inferring it from time windows. One way: include the planned `{stem: sha}` map in the lift effect's recorded input, or add `seeder` to the seed intake signal body. Then exempt only stems named by this seeder's own lift intent whose `ticket_intake` commit on main matches the planned sha. Otherwise, drop the partial-intake exemption and rely only on prior `seed_lift` signals, as the ticket specifies. Add a test where another seeder's intake lands while this seeder's lift is open, and assert that the foreign stem still gets the collision finding.)
