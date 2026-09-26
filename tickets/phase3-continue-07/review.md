---
verdict: snag
reviewed_sha: cbb70a4b50924260b07753e798102a74f2c08535
produced_by_spec_version: '1.0'
produced_at_sha: cbb70a4b50924260b07753e798102a74f2c08535
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The emitted seeds and most pins are right. The pinned sizes match the base commit, and Context, fences and ownership are exact. However, the checks on phase3-continue-08 skip several obligations that acceptance criterion 5 says the test must prove the continuation carries.

## Findings
- correctness_review at tests/test_seeded_phase3_07.py:169: The `PAUSE_FENCES == {owns + hooks}` assertion only compares two module constants with each other. It never reads the phase3-continue-08 ticket. Acceptance criterion 5 says the test must require the continuation to carry the exact pause-pair fences. If the sentence 'Derive each pause seed fence as its owns followed by its hooks' were deleted from the ticket, or the ticket named different fences, this test would still pass. (paved road: Assert against the ticket's Scope in text. Check that the fence-derivation requirement is present (e.g. 'fence as its owns followed by its hooks'), or check that the ticket states or derives each PAUSE_FENCES tuple from the parsed pause_ownership block. Do not compare the constants with each other.)
- correctness_review at tests/test_seeded_phase3_07.py:157: The continuation obligations the ticket lists are not asserted against phase3-continue-08's text. The unchecked ones are: confirmed seed status for the pause seeds, 'every existing fence path in Context', the exact new-path owners, and successor suffix equality. The ticket prose does currently say these things ('Author confirmed', 'The pause seeds include their now-existing predecessor paths in Context', 'exact new-path owners', 'successor suffix equality'), but the test would not catch their removal. Only tier, budgets, cap, headroom and the size map are checked. (paved road: Add phrase assertions on `scope` for 'confirmed', 'exact new-path owners', 'successor suffix equality', and the existing-fence-paths-in-Context requirement for the pause seeds. That pins every obligation in acceptance criterion 5.)
- correctness_review at tests/test_seeded_phase3_07.py:170: The suffix check takes the second yaml block in Scope in by position (`re.findall(...)[1]`). The ownership check just above finds its block by content. If a yaml block is inserted or reordered, the suffix check would parse the wrong block, or fail with a misleading error, instead of pinning the successor list. Low severity: it fails closed, but it is brittle. (paved road: Select the block by content, the same way the ownership block is selected. For example, take the one yaml block from `_yaml("phase3-continue-08")` that is a list, and compare it with SUCCESSOR.)
