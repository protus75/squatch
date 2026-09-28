## Outcome
premise_failed

## Surprises / judgment calls
The prior findings were checked against the current tree rather than accepted as authority. The committed reliability report and missing predecessor Context are repaired, but section 20's Phase 5 registry still has authoring defects.

## Dead ends
`retro-box-activation` requires tombstone auto-reopen to affect triage/authorship, including the draft-state override and a journal-before-mutation production route, but its exact fence omits `squatch/triage.py`, `squatch/author.py`, `squatch/policy.py`, and the relevant composition roots. The current tree constructs independent `Box` instances in those paths, and `Author.run` hard-codes `reopened=False`.

The same registry requires one `retro_finding` per proposal without defining a per-proposal dedup identity, while `Box.enqueue` deduplicates on a signature that normalizes digits and removes path-bearing tokens. It also binds the live retro hook without naming or supplying the LLM/Driver dependency that renders model output into the Markdown receipt. Repairing these contracts requires editing `SQUATCH_PLAN.md` and regenerating this ticket, but the scope fence permits only `tickets`, `tests/test_phase4_exit.py`, and `tests/test_seeded_phase5_core.py`; Scope out forbids changing the registry. Verification was not run because the required seed and test outputs cannot be validly authored from the defective registry.

## Second problems filed

## Resolved engine/model
OpenAI Codex / GPT-5

## Predicted vs actual
Expected 75m; actual approximately 15m before the authoring defect was confirmed.
