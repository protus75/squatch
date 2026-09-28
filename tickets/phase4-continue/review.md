---
verdict: snag
reviewed_sha: 236276c04a8351d37a2fb0052b3b20e372af2eac
produced_by_spec_version: '1.0'
produced_at_sha: 236276c04a8351d37a2fb0052b3b20e372af2eac
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The seeded test meets every acceptance criterion, and the checks are green. One defect: it compares the pinned authoring-time Context sizes against the live files, so it will go red as soon as watchdog-detector or watchdog-activation edits a fenced file, and neither ticket may touch this test.

## Findings
- correctness_review at tests/test_seeded_phase4_01.py:242: `test_authoring_sizes_and_max_effort_headroom` loops over `EXISTING_AT_AUTHORING` and asserts `len((REPO / path).read_text()) == size`. Several of those paths are in the fences of the tickets this admission authors: `squatch/watchdog.py` (1008) and `tests/test_watchdog.py` (1018) belong to watchdog-detector, which must implement the detector there. `squatch/notify.py`, `squatch/serve.py`, `tests/test_notify.py`, `tests/test_serve.py` and `squatch/providers.py` are hooks of watchdog-activation. When either ticket merges, this test fails on `uv run pytest -q`. Both tickets run that command in verification, and this file is outside both fences. The drain stalls on inherited red. The same defect was already fixed in phase3_11 (commit 04cf421). The plan now says these sizes are synthetic historical fixtures and that the test MUST NOT compare them with later live file sizes. (paved road: Delete the live-size comparison loop (lines 242-243). Keep `EXISTING_AT_AUTHORING` only as the synthetic render fixture used to build `context`, and add a why-comment like the one in tests/test_seeded_phase3_11.py. Also check the other tests for live-file dependence: `test_requisition_lint_without_files_created_by_this_admission` and the delimiter scan in `test_context_closure_delimiters_and_new_path_ownership` read live content. That is acceptable only while those files can never gain the delimiter or disappear. Otherwise limit those checks to what is invariant under the sibling tickets' allowed edits.)
