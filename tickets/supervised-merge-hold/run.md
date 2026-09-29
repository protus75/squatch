## Outcome
premise_failed

## Surprises / judgment calls
The plan already specifies this behavior; no plan change was needed. Reused only fenced files from the earlier reviewed implementation, then fixed candidate-base regate identity on every admission path, effective-rung terminal routing, and the daemon-soak reader. The existing admit_delivery three-value contract is retained uniformly; HELD authority comes from the journal, with no tuple-length fallback or second admission path. Both fresh offers and carried retry offers exclude held stems. Resume refuses supervised holds; only identity-bound confirm reaches release.

Committed implementation and regressions as 132722bba257202c4066b803574d89cac547d867. The exact focused Verification command passed 190 tests. Additional restart-timer verification passed 8 tests. The exact full Verification command on the committed tree exited 1: 1688 passed, with only the base-confirmed historical render test failing (101.99s). Focused coverage exercises the actual offline confirm CLI composition, live operator and machine confirms, stale lifecycle/hold/stem identities, preserved cap draws, restart custody, bootstrap exemption, moved-main regating, failed-release harvest, conflict rework, dispatch exclusion, and escalated terminal routing.

## Dead ends
The first full Verification run exposed two committed-artifact assertions while edits were uncommitted, two restart checks needing the journal projection's closed property, and one historical render overflow. Committing resolves the artifact checks; forwarding the existing closed property resolves the restart checks.
The render overflow is outside the fence: tests/test_seeded_phase6_02.py::test_every_emitted_ticket_renders_with_real_context_at_max_effort renders phase6-continue-03 at 120131 characters against a 120000 limit. Reproduced the same failure with every tracked implementation edit temporarily restored to base commit 591b6c910f0b78c4d8b9ea373e010094629aa3ba, then restored the candidate. The implicated historical test, SQUATCH_PLAN.md, specs/implement.md, tests/test_seeded_phase6_01.py, and tickets/phase6-continue-03/ticket.md are outside this ticket's fence. No limit, seed, plan, or test bypass was changed. Following the explicit On-failure rule, retained the completed work as a commit rather than claiming implemented.

## Second problems filed
Base-confirmed historical render failure: tests/test_seeded_phase6_02.py:119, phase6-continue-03 exceeds max-effort requisition headroom by 131 characters. Filed here for follow-up; the historical render test needs its own scoped correction using authoring-time fixtures. No adjacent files were edited.

## Resolved engine/model
OpenAI / GPT-6 (Codex); exact serving model identifier unavailable.

## Predicted vs actual
Expected 75m; actual approximately 10m, including both required verification commands and base reproduction of the out-of-fence blocker.
