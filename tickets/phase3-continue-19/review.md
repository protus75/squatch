---
verdict: snag
reviewed_sha: d5669216c8c931f4dd5a564e06ec4b3702f9fe5b
produced_by_spec_version: '1.0'
produced_at_sha: d5669216c8c931f4dd5a564e06ec4b3702f9fe5b
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The seeded test pins most of the daemon-soak and phase3-continue-20 contract. Acceptance criterion 4 is only partly met: the test never checks the phase3-exit -> soak-run dependency edge or that the tail authors phase3-exit alone.

## Findings
- correctness_review at tests/test_seeded_phase3_19.py:183: Criterion 4 requires the test to prove that the phase3-continue-20 ticket pins the terminal phase3-exit batch, including its dependency edges. test_terminal_continuation_pins_soak_run_and_phase3_exit_contract checks "KNOWN-HARD high/high" and "phase3-exit` is" as separate substrings, and nothing asserts that phase3-exit depends on soak-run. The only `depends on `soak-run`` assertion is anchored to phase3-continue-21. If the ticket's phase3-exit sentence named a different predecessor, such as phase3-continue-21, every test would still pass. The test also never pins that the tail authors `phase3-exit` alone; it only checks the substring "no successor". (paved road: Assert the exact clauses the ticket states: "`phase3-exit` is KNOWN-HARD high/high, depends on `soak-run`" and "authors `phase3-exit` alone and no successor". Then the phase3-exit edge, its tier, and the single-exit tail are each pinned by a statement that cannot be satisfied by some other seed's text.)
