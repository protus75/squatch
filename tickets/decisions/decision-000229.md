---
id: decision-000229
kind: decision
link: box-000229-5eca38b5
reopen_after_days: 90
message: box-000229-5eca38b5
---
No ticket. The message wants the section 19 seed-enumeration test to land along with batch 3-4, so that the known-hard tier/effort pin has a reader. That test already exists and is merged. tests/test_seeded_phase2.py is the 'Phase 2 seed enumeration test (SQUATCH_PLAN.md sections 13, 18, 19)' (docstring, line 1). It was added by bootstrap commit c575029 (deliverable 17, batch 4 of 4). It declares `KNOWN_HARD = {requisition-review-call, requisition-review-author, requisition-review-seed, phase2-exit}` with `EVIDENCE_SECTION = "19"` (:63-65). At :159-163 it asserts that every known-hard seed carries `agent_effort: high` and cites plan section 19, and that every other seed stays at `medium`. So the pin the message is about has its reader. It covers the three requisition_review seeds the message names and also the exit seed. Those seeds have since merged. A tombstone does not fit, because the test was produced by a bootstrap deliverable and not by a rendered ticket, and no rendered Goal or decision names the enumeration test.

Evidence: tests/test_seeded_phase2.py:1 (docstring naming it the Phase 2 seed enumeration test), :59-65 (KNOWN_HARD set with the three requisition-review seeds plus phase2-exit, evidence section 19), :159-163 (high-effort and section-19 citation assertions); added in c575029. Message origin bootstrap-ingest, evidence None. Reopen if a regeneration drops tests/test_seeded_phase2.py or its KNOWN_HARD assertions, or if a later phase's seeding names known-hard seeds and no enumeration test pins them.
