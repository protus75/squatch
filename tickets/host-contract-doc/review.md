---
verdict: snag
reviewed_sha: f32e3b701751dfe9343e35f6a4a15c00d2f39968
produced_by_spec_version: '1.0'
produced_at_sha: f32e3b701751dfe9343e35f6a4a15c00d2f39968
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The YAML example matches squatch/config.py's schema, the diff stays inside the fence, and the checks are green. One defect: the documented managed-block begin marker doesn't match what squatch/hostfiles.py renders and accepts, and the new test locks in the wrong literal.

## Findings
- correctness_review at docs/host-contract.md:101: The doc says the managed block is delimited by the literal `<!-- squatch:core begin -->`. squatch/hostfiles.py:83 only accepts `<!-- squatch:core begin version=N sha256=<64 hex> -->`, and hostfiles.py:100 renders that form. If a host copies the documented marker, the engine refuses it as malformed, so the published ownership contract is wrong. tests/test_host_contract.py:68 asserts the wrong literal, which pins the error. This is only a note-level risk if hosts never write the marker by hand, but the doc presents it as the contract, so I'm reporting it. (paved road: Describe the begin marker as `<!-- squatch:core begin version=<N> sha256=<digest> -->`, rendered by Squatch and not written by hand. Keep `<!-- squatch:core end -->` as the end marker. Change the test to assert the attributed begin form, or just the `<!-- squatch:core begin` prefix plus the version/sha256 attributes, instead of the bare literal.)
