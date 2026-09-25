---
verdict: snag
reviewed_sha: 2a481d0b33e33f42692025d658a141b6eec21041
produced_by_spec_version: '1.0'
produced_at_sha: 2a481d0b33e33f42692025d658a141b6eec21041
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
Triage, the spec, the CLI verb and the drain pin meet their criteria. But `go_binds` compares the recorded baseline against an identity built over all four tiers. `eval/harness.py` records only the tiers it ran, so a real GO signal in the harness shape can never bind, and the policy test cannot catch this because it builds its baseline with `_identity` itself.

## Findings
- correctness_review at squatch/policy.py:23: `_identity` resolves review and author for every tier in `TIERS`, and `go_binds` then requires `baseline.body['identity'] == identity` exactly. But `eval/harness.py` (`baselined_identity(registry, [tier])`, `ReviewBaselineSignal.tiers`) records identity only for the tiers the eval ran, currently just `specs/review.md`'s one tier. So a `review_baseline` signal in the shape the harness actually writes always compares unequal, and `go_binds` is false forever, even with an unchanged routed identity. The ticket asks for a match against 'the shape eval/harness.py records', and that shape is not met. `tests/test_policy.py` hides the problem: it builds the GO body from `policy._identity(cfg)` rather than the harness shape, so the check is circular. The ticket's 'at every tier' wording could be read either way; the harness shape is the concrete standard it cites, so I treat this as a defect. (paved road: Build the current identity over the tiers the signal records: read `baseline.body['tiers']` and fail closed to false if it is missing or empty. Mirror `baselined_identity`, `spec_versions` and `spec_major` in `eval/harness.py`, including refusing (false) on a `PLACEHOLDER` row, and compare `identity` and `spec_major` against that. In `tests/test_policy.py`, build the GO body the way the harness does: `baselined_identity(Registry(cfg), [tier])` plus `tiers`, with verdict overridden to `GO`. Keep the drift case: change one recorded review row's model and assert false.)
