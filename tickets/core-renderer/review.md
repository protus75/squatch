---
verdict: snag
reviewed_sha: b7c2aabcf63f23872dda1882f1fe70b917014df5
produced_by_spec_version: '1.0'
produced_at_sha: b7c2aabcf63f23872dda1882f1fe70b917014df5
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The renderer, CLI registration and tests meet the ticket's structure and stay inside the scope fence. One defect remains: render can write a file that it refuses on the next pass, which breaks the ticket's idempotence and fail-closed rules.

## Findings
- correctness_review at squatch/hostfiles.py:21: managed_block (and so render) accepts any `core` text without checking it. If `core` contains marker-like text (case-insensitive `squatch:core`, e.g. a conduct rule that mentions 'the `squatch:core` block', or a literal `<!-- squatch:core end -->` line), the first render succeeds and inserts it. The next render over that output finds more than two marker-like matches, or two end markers, and raises ManagedBlockRefusal. So render(render(x, core), core) != render(x, core): the renderer produces a file that its own marker check calls corrupt. That breaks section 8's rule that a second render over a clean file is byte-identical, and hits the ticket's 'non-idempotent output' rejection. The idempotence test only uses the core string 'Engine conduct', so it cannot catch this. (paved road: In managed_block, raise ManagedBlockRefusal (or ValueError) when `_MARKER_LIKE.search(core)` matches, so the renderer never emits a block it would later refuse. Add a test in tests/test_hostfiles.py showing that a core containing `squatch:core` is refused at render time rather than on the second pass.)
