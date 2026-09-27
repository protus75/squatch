---
verdict: snag
reviewed_sha: 2bbc384ec56c2cf5ebcbac4ef9405f4cda9240ae
produced_by_spec_version: '1.0'
produced_at_sha: 2bbc384ec56c2cf5ebcbac4ef9405f4cda9240ae
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The seeds, dependencies, ownership, and successor suffix look right, and every changed path is inside the fence. The problem is that tests/test_seeded_phase3_15.py checks the live repo against authoring-time sizes. The first seed it authors (journal-roll edits squatch/journal.py) and any later growth of section 20 will turn the full suite red, and nobody downstream is fenced to fix it.

## Findings
- correctness_review at tests/test_seeded_phase3_15.py:128: The test asserts `(REPO / path).stat().st_size == EXISTING_AT_AUTHORING[path]` against the live files. journal-roll puts squatch/journal.py in its fence and is required to change it, and storm-producer-wiring/storm-notification-activation will change squatch/box.py, squatch/daemon.py, and squatch/__main__.py. Once any of those lands, this test fails in `uv run pytest -q`. The failing seed cannot repair it because tests/test_seeded_phase3_15.py is outside its fence. The ticket asks for authoring-time sizes pinned as historical fixtures, not an equality check on the current file sizes. The predecessor (tests/test_seeded_phase3_14.py) pins the sizes only in the dict and uses them for the render fixture. (paved road: Drop the live st_size equality. Keep EXISTING_AT_AUTHORING as the pinned historical fixture that feeds the render-headroom computation, following the test_seeded_phase3_14.py pattern: check that each Context path is_file and is a member of EXISTING_AT_AUTHORING.)
- correctness_review at tests/test_seeded_phase3_15.py:179: `assert len(section) == PLAN_SECTION_AT_AUTHORING` fails as soon as plan section 20 changes at all. At line 189 the render bound is checked on the raw `len(rendered)`, which includes the live section, so later section-20 growth is charged to these historical fixtures. The ticket requires the opposite: 'pin authoring-time section 20 length so later growth is not charged to historical fixtures'. (paved road: Pin the constant on its own (`assert PLAN_SECTION_AT_AUTHORING == 20430`). Compute `historical_length = len(rendered) - max(0, len(section) - PLAN_SECTION_AT_AUTHORING)` and assert `historical_length <= limit`, as test_seeded_phase3_14.py does.)
- correctness_review at tests/test_seeded_phase3_15.py:126: The ticket says to keep delimiter-bearing prompt-spec sources out of every Context. The test only excludes two named paths (squatch/specs.py, specs/implement.md). It dropped the predecessor's content check that no Context file contains `<<<squatch:`, so a delimiter-bearing Context file added by a later edit would go undetected. Lower confidence: the acceptance list does not name this check explicitly, but Scope in requires it. (paved road: Inside the per-Context-path loop, add `assert "<<<squatch:" not in (REPO / path).read_text()`, as test_seeded_phase3_14.py does.)
