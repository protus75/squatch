---
verdict: snag
reviewed_sha: 2efea39042b6ec73b5b1cbecf4fd23c24acdc6d8
produced_by_spec_version: '1.0'
produced_at_sha: 2efea39042b6ec73b5b1cbecf4fd23c24acdc6d8
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The new test covers every acceptance criterion and stays inside the fence, but one assertion breaks when the successor is implemented. It checks that phase4-exit's two new files are absent from the real repo, so once phase4-exit creates them this test fails, and phase4-exit is not allowed to edit this file.

## Findings
- correctness_review at tests/test_seeded_phase4_05.py:108: `if owner == EXIT: assert not (REPO / path).exists()` checks that `tests/test_phase4_exit.py` and `tests/test_seeded_phase5_core.py` do not exist in the live repo. phase4-exit's whole job is to create those two files. Once it does, this test fails, and so does phase4-exit's own required `uv run pytest -q` verification. phase4-exit's fence (`tickets`, `tests/test_phase4_exit.py`, `tests/test_seeded_phase5_core.py`) does not include this file, so it cannot fix the assertion. That breaks the ticket's rule to preserve predecessor tests and bind invalidated assertions to their editing owner, and it traps the terminal admission behind a red suite it cannot repair. The predecessor pattern (`tests/test_seeded_phase4_01.py:177`) checks non-existence under `tmp_path`, never under `REPO`. (paved road: Remove the live-repo `exists()` assertion. Prove new-path ownership through the fence checks alone (the path is in the owner's `scope_fence`, absent from the other ticket's fence, and absent from every Context). If an authoring-time non-existence proof is wanted, follow `test_seeded_phase4_01.py` and assert it against a `tmp_path` fixture built from `EXISTING_AT_AUTHORING`, not against `REPO`.)
