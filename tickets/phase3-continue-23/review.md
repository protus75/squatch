---
verdict: snag
reviewed_sha: 177aff3ca32e5a563e74b9d65cac7a7ba9755ddc
produced_by_spec_version: '1.0'
produced_at_sha: 177aff3ca32e5a563e74b9d65cac7a7ba9755ddc
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The identity, fence, Context, admission and render-headroom pins are sound, and the committed phase3-exit ticket matches the plan. The fourth acceptance criterion is not met: the test never pins the Phase 4 core identities, dependency edges or ordered suffix against the exit ticket or the section 20 registry.

## Findings
- correctness_review at tests/test_seeded_phase3_23.py:108: `assert PHASE4_CORE == (...)` and `assert PHASE4_SUFFIX == (...)` compare module constants with literals copied from the same file, so they are always true. PHASE4_SUFFIX is never checked against anything. The finite ordered suffix (watchdog-detector plus watchdog-activation, then provider-cooldown-failover, reliability-battery, reliability-run, phase4-exit last) is therefore not pinned. The exit ticket could reorder, drop or invent a suffix stem and this test would still pass. (paved road: Check the ordered suffix against the phase3-exit ticket's Scope in: every PHASE4_SUFFIX stem must appear, in order, e.g. with strictly increasing `exit_scope.index(stem)`. Pin the same order against the SQUATCH_PLAN.md 'Phase 4 boundary registry' paragraph, so the test fails if the exit ticket drifts from section 20. Delete the self-comparisons.)
- correctness_review at tests/test_seeded_phase3_23.py:104: The Phase 4 dependency edges are never asserted, though the criterion requires them. Section 20 says watchdog-event-stream and notify-transport each depend on phase3-exit, and phase4-continue depends on both machinery stems. The ownership-fence check only tests that each path appears somewhere in the exit Scope in, anywhere and in backticks. It does not tie a path to its owning stem, so a path assigned to the wrong seed (e.g. squatch/config.py under watchdog-event-stream) would pass. (paved road: Pin each core seed's dependency edges and its owned-path set per stem. Either parse a structured ownership/depends block from the exit ticket's Scope in, or match each stem's own sentence. Compare the result against a per-stem mapping taken from the section 20 registry text.)
