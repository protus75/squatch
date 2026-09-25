---
verdict: snag
reviewed_sha: 99d9c44ff19ae306a565cb12dcd403963c394f9f
produced_by_spec_version: '1.0'
produced_at_sha: 99d9c44ff19ae306a565cb12dcd403963c394f9f
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The seed path, SeedSafety and the lift are sound in shape, but three acceptance criteria are untested or only partly asserted. SeedSafety also reads checks.json from the canonical working tree instead of the committed blob that the ticket requires.

## Findings
- correctness_review at tests/test_terminal.py: Acceptance criterion 5 (second half) is unmet: no test runs an ordinary, non-seeding ticket and asserts that the journal holds no `seed_lift` signal and no effect whose key starts with `llm/requisition_review/`. The new terminal tests all drive seeding runs. (paved road: Add a test_terminal.py case that drives an ordinary ticket to merge. Assert that no signal has body kind `seed_lift` and that no journal event key starts with `llm/requisition_review/`.)
- correctness_review at tests/test_merge.py:352: Acceptance criterion 6 is only partly met: the parametrized test covers tampered and matching seeds, but no test covers 'an admission with no `seed_lift` signal runs no seed check'. SeedSafety is always built and always shows up in the MERGE-SAFETY gate run, and nothing asserts that it passes without inspecting checks.json or main blobs when there is no signal. (paved road: Add a test_merge.py case that admits an ordinary branch with no `seed_lift` signal. Assert that the admission is ok and that the requisition_review gate result is a finding-free pass, for example with no checks.json present so a read attempt would fail.)
- correctness_review at tests/test_terminal.py:311: Acceptance criterion 4 requires that 'a batch of four seeds ends `gate_failed` on the cap finding with no review call made'. The four-seed half asserts only EXIT_TICKET and that no requisition_review request was made. It never asserts the `gate_failed` transition or the cap finding in checks.json, and it does not check that the branch review was never called either. (paved road: After the second `drive.run()`, assert that `drive.transitions()[-1]["to"] == "gate_failed"` and that checks.json has a `requisition_review` finding whose message names `seeding.max_seeds_per_admission` and whose road carries the `-continue` split. Also assert that no review-surface request was made.)
- correctness_review at squatch/merge.py:120: The ticket requires SeedSafety to check 'the run's committed `tickets/<stem>/checks.json`'. The code instead reads `(self._repo / checks_rel).read_text()` from the canonical checkout's working tree, raw and outside the filesystem seam. If the working-tree copy is edited, stale or missing, it can diverge from what is committed on main, so the approval check reads bytes that are not on record. (paved road: Read the committed blob through git, for example with `self._git.show(self._repo, f"main:{checks_rel}")` or the equivalent Git wrapper verb. Treat a missing blob as a failing finding with SEED_SAFETY_ROAD.)
