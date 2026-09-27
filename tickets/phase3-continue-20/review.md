---
verdict: snag
reviewed_sha: e6db70391f06316f43dcb142adbc6a27caf7e4dc
produced_by_spec_version: '1.0'
produced_at_sha: e6db70391f06316f43dcb142adbc6a27caf7e4dc
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The seeded test pins the batch identities, fences, Context, sizes (they match the files on disk) and the max-effort render. Acceptance criterion 3's downstream edges, tiers and owners are only partly pinned, and one assertion always passes because it checks only a constant.

## Findings
- correctness_review at tests/test_seeded_phase3_20.py:153: Acceptance criterion 3 requires pinning downstream owners/edges/tiers. The successor test pins the daemon-soak-runner and phase3-continue-22 ownership YAML, the `soak-run` -> `daemon-soak-runner` edge and the KNOWN-HARD label. Nothing pins these downstream contracts that the successor ticket states: daemon-soak-runner depends on `serve-activation` and is KNOWN-DEEP high/high; phase3-continue-22 depends on `daemon-soak-runner` and is medium/medium; soak-run is medium/medium no-code and produces only `tickets/soak-run/daemon-soak-report.json`; phase3-exit is high/high, depends on `soak-run` and owns `tickets`, `tests/test_phase3_exit.py` and `tests/test_seeded_phase4_core.py`. phase3-exit ownership appears only in the local NEW_PATH_OWNERS constant, which is never checked against any ticket. The successor ticket's text could drop or change any of these edges or tiers and the test would still pass. (paved road: In test_successor_pins_runner_and_terminal_suffix_after_removing_only_serve, assert the exact successor Scope-in phrases for each downstream member's edge and tier. Examples: "`daemon-soak-runner` depends on `serve-activation`, is KNOWN-DEEP high/high", "`phase3-continue-22` depends on `daemon-soak-runner`, is medium/medium", "medium/medium no-code `soak-run`", "produces only `tickets/soak-run/daemon-soak-report.json`", "the exit depends on `soak-run`, owns `tickets`, `tests/test_phase3_exit.py`, and `tests/test_seeded_phase4_core.py`". Also add a high/high tier phrase for phase3-exit.)
- correctness_review at tests/test_seeded_phase3_20.py:123: `assert set(CONTEXT["serve-activation"]) - {"squatch/daemon.py", "squatch/__main__.py"}` computes a set difference between two constants and asserts only that the result is non-empty. It is always true and checks no ticket content, so it pins nothing about the embedded production roots versus the predecessor tests. (paved road: Replace it with an exact check against the authored ticket. For example: assert the two production roots are exactly `{p for p in activation.context if p.startswith("squatch/")} == {"squatch/daemon.py", "squatch/__main__.py"}`, and the predecessor tests are exactly the remaining four `tests/` paths. Or delete the line.)
