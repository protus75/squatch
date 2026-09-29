---
verdict: snag
reviewed_sha: d7962a9dcf281c5072ca5507e3174f44f9e4ab2e
produced_by_spec_version: '1.0'
produced_at_sha: d7962a9dcf281c5072ca5507e3174f44f9e4ab2e
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The phase5-exit ticket text and its terminal registry are pinned correctly, and checks are green. The seeded test does not meet acceptance criterion 4 (Context fixtures and exclusions), and its render-headroom proof leaves out the exit ticket's own Context files.

## Findings
- correctness_review at tests/test_seeded_phase5_04.py:134: Acceptance criterion 4 is not met. The file never asserts that `phase5-continue-04` embeds merged `tests/test_seeded_phase5_02.py` as its Context. It never checks that this Context excludes the same-admission `tests/test_seeded_phase5_04.py` and the sibling-new `tests/test_seeded_phase5_03.py`. It also asserts nothing about `phase5-exit`'s own `## Context` list: that every path existed at authoring and that none is a same-admission new path such as `tests/test_phase5_exit.py`, `tests/test_seeded_phase6_core.py` or `tests/test_seeded_phase5_04.py`. No test in the file reads `ticket.context` at all. (paved road: Follow `test_context_partition_synthetic_sizes_and_render_headroom` in the merged `tests/test_seeded_phase5_02.py`. Assert `_ticket("phase5-continue-04").context == ("tests/test_seeded_phase5_02.py",)` and that the file exists. Assert the context is disjoint from {`tests/test_seeded_phase5_03.py`, `tests/test_seeded_phase5_04.py`}. Pin `_ticket(EXIT).context` to its exact tuple, assert each path existed at authoring, and assert it is disjoint from the exit's new fence paths and from `tests/test_seeded_phase5_04.py`.)
- correctness_review at tests/test_seeded_phase5_04.py:129: The max-effort render-headroom proof for `phase5-exit` renders with an empty `context` block. The authored ticket declares three Context files: `tests/test_retro_box.py` (~29.9 KB), `tests/test_baseline.py` (~5.1 KB) and `tests/test_seeded_phase5_03.py` (~8.0 KB). Together that is about 43 KB of the 120,000-char bound, so the assertion does not measure what the exit's implement stage will actually render. Criterion 1 ('bounded budget') and criterion 3 ('max-effort render headroom') are only nominally proven. (paved road: Render with the exit's declared Context, as `tests/test_seeded_phase5_02.py` does with `_context(...)`. Use a pinned `EXISTING_AT_AUTHORING` synthetic-size map covering the three paths, feed `_context(_ticket(EXIT).context)` into the `context` DataBlock, and assert the result stays within `RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM`.)
