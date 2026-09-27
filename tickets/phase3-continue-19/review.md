---
verdict: snag
reviewed_sha: 7cdf4b3432612cb71cb6cc69739c08cc2e3dc40a
produced_by_spec_version: '1.0'
produced_at_sha: 7cdf4b3432612cb71cb6cc69739c08cc2e3dc40a
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diff stays inside the fence and all checks are green. It does not fully meet the fourth acceptance criterion: nothing asserts the soak-run and phase3-continue-21 tiers or any budget, and the future fences are checked by membership only, not exact equality.

## Findings
- correctness_review at tests/test_seeded_phase3_19.py:136: Criterion 4 requires proving that phase3-continue-20 pins the soak-run and terminal batches' tiers and budgets. test_terminal_continuation_pins_soak_run_and_phase3_exit_contract asserts only 'KNOWN-HARD high/high' for phase3-exit. It never asserts that soak-run (or the phase3-continue-21 tail) is medium/medium, and it never asserts the 75m/150m budgets or the `drain.max_ticket_minutes` bound for any authored-next seed. If phase3-continue-20 were edited to make soak-run high/high or change its budgets, this test would still pass. (paved road: Add phrase or structured assertions on the phase3-continue-20 Scope in text for the medium/medium tier of soak-run and phase3-continue-21 (e.g. 'Both are medium/medium') and for '75m/150m budgets within `drain.max_ticket_minutes`', plus the cap-3 phrase.)
- correctness_review at tests/test_seeded_phase3_19.py:109: The future ownership contract parsed from phase3-continue-20 is only checked for membership (`path in owns`), so the fences are never pinned exactly. The ticket must fence soak-run ONLY to `tickets/soak-run/daemon-soak-report.json` with code changes forbidden, but a future block that added extra owns or hooks to soak-run, phase3-continue-21, or phase3-exit would still pass. The 'changes no code' phrase check does not catch a widened fence. (paved road: Assert that the parsed `future` ownership mapping equals an exact expected dict: soak-run owns [tickets/soak-run/daemon-soak-report.json] hooks []; phase3-continue-21 owns [tickets, tests/test_seeded_phase3_21.py] hooks []; phase3-exit owns [tickets, tests/test_phase3_exit.py, tests/test_seeded_phase4_core.py] hooks []. This mirrors the exact `contract == OWNERSHIP` check already used for phase3-continue-19.)
