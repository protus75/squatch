---
verdict: snag
reviewed_sha: 1fe294e8e21bcfef5e0a803237121f14dee3eb3b
produced_by_spec_version: '1.0'
produced_at_sha: 1fe294e8e21bcfef5e0a803237121f14dee3eb3b
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The seeds and pins mostly match the ticket, and every check passed. Two acceptance criteria are only partly pinned: the new-path registry-owner assertion is a tautology, and nothing pins that the hold is wired into the live drain's CLI composition root.

## Findings
- correctness_review at tests/test_seeded_phase3_17.py:114: The acceptance criterion requires pinning new-path registry owners. The assertion `NEW_PATH_OWNERS == {...}` compares a module constant to a copy of the same literal, so it can never fail and checks nothing about the tickets. Nothing checks that tests/test_storm_hold.py sits in storm-dispatch-hold's fence as an owned path. Nothing checks that checkpoint-push owns squatch/checkpoint.py and tests/test_checkpoint.py in phase3-continue-18's ownership YAML, or that phase3-continue-19 owns tests/test_seeded_phase3_19.py. Nothing checks that these new paths are absent from the repo at authoring time. (paved road: Replace the self-comparison with checks derived from the tickets. For each new path, assert it appears in the `owns` list of its named owner: for the hold, use `ticket.scope_fence`; for checkpoint-push and phase3-continue-19, parse the ownership YAML in phase3-continue-18's Scope in. Also assert `not (REPO / path).exists()` for the paths that must be new at authoring.)
- correctness_review at tests/test_seeded_phase3_17.py:147: Acceptance criterion 5 requires pinning resume and crash recovery in the production root. The ticket's Definition of rejected names 'absent production-root ownership' and 'dormant-only hold construction'. The phrase list checks resume and rehydrate wording, but it never checks the hold ticket's binding sentence, 'Bind the journal-derived per-stem hold through the live drain's CLI composition root'. So the seed could lose its production-root requirement and the test would still pass. (paved road: Add 'live drain\'s CLI composition root' (and 'defer production activation' from Scope out) to the pinned phrases for storm-dispatch-hold.)
- correctness_review at tickets/storm-dispatch-hold/ticket.md: None of the authored hold ticket's acceptance criteria asks for proof that the hold is bound through the live drain's CLI composition root (squatch/__main__.py / drain.py). The Scope in requires the binding, but an implementer could meet every acceptance criterion with a hold built only in unit tests (dormant-only). This is the case the commissioning ticket's Definition of rejected names. I'm moderately confident this needs a fix: Definition of rejected does say 'dormant-only construction', but acceptance criteria are what the reviewer checks one by one. (paved road: Add an acceptance criterion to the hold ticket: `tests/test_storm_hold.py` proves the per-stem hold is bound through the live drain's CLI composition root, so a drain assembled through that root suppresses the tripped stem and resumes it. Then pin that criterion's text in tests/test_seeded_phase3_17.py.)
