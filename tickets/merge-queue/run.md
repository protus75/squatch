## Outcome
ok

## Surprises / judgment calls
The branch began clean at 944799a7, without the queue. Restored the four scoped files from prior implementation d9a3633b, then corrected its literal-prefix matching and centralized conflict unwind. Section 20 and the existing scope-fence rule already specify the required behavior; no plan defect or plan change was needed.

Strategy declarations now match exact paths or descendants, with glob characters treated literally. Refused conflict resolution aborts exactly once. An abort GitError produces a CandidateRebaseFinding, journals conflict facts, releases the serial slot, and emits no Rework handoff. Successful unwind publishes the shared typed handoff only after releasing the slot. Other resolution exceptions still unwind before propagating; Git errors become typed refusals.

Kept the prior additive Git seams, including the opportunistic abort for non-conflict rebase failures and non-interactive continuation. The later after-start failure lesson supersedes the earlier suggestion never to attempt abort on a dirty candidate. AST comparison confirmed all pre-existing Git methods and the existing Merge/Pipeline composition are unchanged. Queue activation and the production Rework consumer remain later registry deliverables; a direct consumer fixture proves the shared handoff contract.

Committed only the four fenced code/test paths in 180392093f6ff77e6a1792b365e9f53ce96e92b7. Verification on that commit: uv run pytest tests/test_mergequeue.py -q exited 0 (23 passed); uv run pytest -q exited 0 (860 passed). Regression coverage includes nested prefixes, literal glob entries, both abort-failure paths, and conflict-inspection failures before and after continuation.

## Dead ends
An initial read-only Python inspection command had a syntax typo; corrected it before inspecting git state. No implementation approach was abandoned.

## Second problems filed
None found.

## Resolved engine/model
OpenAI / GPT-6 (Codex); exact serving variant not exposed.

## Predicted vs actual
Expected 120m; actual approximately 6m, including recovering the prior implementation, corrections, tests, and commit.
