---
verdict: snag
reviewed_sha: dd7e7f1a755a68d625de057b4b490352dd1466be
produced_by_spec_version: '1.0'
produced_at_sha: dd7e7f1a755a68d625de057b4b490352dd1466be
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
Row 1, the pinned edges, the shrinking suffix, the KNOWN-DEEP/KNOWN-HARD tiers, terminal custody and the max-effort render are all covered, and the check report is green. However, the test never pins the owner/fence or Context rule for the numbered continuation rows phase6-continue-03 through phase6-continue-08, which acceptance criterion 2 requires. The authored row-2 ticket only states that contract for phase6-continue-03.

## Findings
- correctness_review at tests/test_seeded_phase6_01.py:205: Acceptance criterion 2 requires the test to pin every remaining row's exact owner/fence and Context/on-demand partition through phase6-continue-08. For phase6-continue-03..08, test_shrinking_suffix_continuation_edges_and_terminal_custody_are_exact checks only their direct `depends` edges. REMAINING and PARTITION_CLAUSES contain no continuation stems. Nothing asserts that a continuation owns only `tickets` plus its matching new `tests/test_seeded_phase6_<nn>.py`, or that its sole Context is the immediately preceding merged Phase 6 seeded test. The row-2 ticket text 'owns only `tickets` plus new `tests/test_seeded_phase6_03.py`, and embeds the immediately preceding merged Phase 6 seeded test as its sole Context' could be deleted and every test would still pass. (paved road: Add a continuation contract table for phase6-continue-03..08 with fence ('tickets', 'tests/test_seeded_phase6_<nn>.py') and the sole-preceding-seeded-test Context rule. Assert each clause appears in the phase6-continue-02 Scope in, the same way PARTITION_CLAUSES is checked for payload rows.)
- correctness_review: The authored tickets/phase6-continue-02/ticket.md (inside the `tickets` fence and committed through intake on this branch's base) states the continuation owner/fence/Context rule only for phase6-continue-03. The commissioning ticket requires every numbered continuation to own only `tickets` plus its matching new seeded test, embed the preceding merged Phase 6 seeded test as its sole Context, and carry the shrinking suffix. That generic rule is not carried forward, so the row-2 contract for phase6-continue-04..08 is incomplete: phase6-continue-03 inherits no stated fence/Context rule to pass on. I'm moderately confident this counts as an incomplete row contract under 'Definition of rejected' rather than something section 20 alone covers. (paved road: Add the generic continuation clause to the phase6-continue-02 Scope in: each numbered continuation owns only `tickets` plus its matching new `tests/test_seeded_phase6_<nn>.py`, embeds the immediately preceding merged Phase 6 seeded test as its sole Context, depends on every payload in its row, and carries the shrinking suffix. Pin that clause in tests/test_seeded_phase6_01.py.)
