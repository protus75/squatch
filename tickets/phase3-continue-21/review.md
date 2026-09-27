---
verdict: snag
reviewed_sha: a3eba249068473f0cf3540018aff66eb44adbdf6
produced_by_spec_version: '1.0'
produced_at_sha: a3eba249068473f0cf3540018aff66eb44adbdf6
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
Most of the contract is pinned correctly: identities, edges, tiers, budgets, cap, fences, Context partition, authoring sizes (they match the base commit), on-demand exceptions, suffix equality and the render bound. But the new-path owner check is tautological, and the downstream phase3-exit ownership is never read from any ticket.

## Findings
- correctness_review at tests/test_seeded_phase3_21.py:123: `assert NEW_PATH_OWNERS == {...}` compares the module constant to a literal copy of itself, so it can never fail and pins nothing against the authored tickets. Nothing in the test checks that `phase3-exit` owns `tests/test_phase3_exit.py` and `tests/test_seeded_phase4_core.py` (plus `tickets`), which the phase3-continue-22 Scope in states in prose. The only phrase checked is the bare token "`phase3-exit`". That leaves acceptance criteria 2 and 3 (new-path owners; downstream owners/edges/tiers) unmet for the exit seed: the continuation ticket could drop or reassign those paths and this test would stay green. (paved road: Delete the self-equality assert. Derive each NEW_PATH_OWNERS entry from the authored artifacts: daemon-soak-runner and phase3-continue-22 from their scope fences, soak-run and phase3-continue-23 from the phase3-continue-22 ownership YAML, and phase3-exit by asserting that the phase3-continue-22 Scope in contains "owns `tickets`, `tests/test_phase3_exit.py`, and" and "`tests/test_seeded_phase4_core.py`" (whitespace-tolerant regex, as the fault-reference checks already do).)
