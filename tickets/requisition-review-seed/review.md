---
verdict: snag
reviewed_sha: 0dab35e603064a04d18f08d7b37f0422fff54e41
produced_by_spec_version: '1.0'
produced_at_sha: 0dab35e603064a04d18f08d7b37f0422fff54e41
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diff meets the acceptance tests and stays inside the fence, but nothing ties the lifted bytes to the bytes that were reviewed: the lift reads the worktree a second time, and SeedSafety accepts any passing entry for the same path, so a lifted seed can reach main without an approval for its bytes.

## Findings
- correctness_review at squatch/stages.py:543: After the check effect returns a passing invoice, `_check` calls `authored_seeds(worktree, stem, self._git)` a second time and lifts whatever the worktree holds at that moment. It does not lift the seed set that `_seed_checks` validated and reviewed inside the check effect. `_lift_seeds` only confirms that `stamp(seed.text)` hashes to `seed.sha`, and `seed.sha` comes from the same re-read, so it proves nothing about the reviewed bytes. The check effect can also be replayed from the journal after a crash, and then the lift reads a worktree the review never saw. SeedSafety in merge.py does not close the gap: it asks whether main's blob matches the lifted sha and whether any passing `requisition_review` entry exists for the path. The `CheckEntry` records no reviewed sha. So a seed whose bytes changed between review and lift, or a stem that was never reviewed, is lifted and then admitted. That contradicts the Goal's 'recorded approval for the bytes now on main'. I'm not certain this can happen in normal serial flow, but no mechanism rules it out. (paved road: Make the reviewed batch the only input to the lift. Record each reviewed seed's blob sha in its `requisition_review` entry, for example by extending the per-seed `path` entry or by carrying the seed map out of the check effect's result. Have `_lift_seeds` refuse any seed whose stem is not in the reviewed set or whose sha differs from the reviewed sha. Have SeedSafety require the passing entry's recorded sha to equal the lifted sha. Add a test that edits a seed file between Check and the lift and shows the lift or admission refuses it.)
