---
verdict: snag
reviewed_sha: e959ccfbd86735088c30fae4fd82fec5785057c4
produced_by_spec_version: '1.0'
produced_at_sha: e959ccfbd86735088c30fae4fd82fec5785057c4
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The production wiring in merge.py looks plausible, but tests/test_mergequeue.py only changes the one migrated assertion. None of the new tests required by several acceptance criteria were added.

## Findings
- correctness_review at tests/test_mergequeue.py: Acceptance criterion 1 is unmet. No test proves that compose_pipeline builds its MergeQueue through compose_merge_queue with the concrete regate, integration and integrate adapters. No test asserts the configured timeout (drain.max_ticket_minutes*60) or the secret-filtered child_env on that queue. The only change to this file is the single migrated assertion. (paved road: Add a test that calls compose_pipeline and asserts: pipeline.merge_queue is an instance of the capturing MergeQueue subtype; its callbacks are the compose_pipeline adapters; its timeout equals config.drain.max_ticket_minutes*60; and its env excludes the configured provider auth variables.)
- correctness_review at tests/test_mergequeue.py: Acceptance criterion 2 is unmet. No test shows that the direct two-argument Pipeline(stages, merge) construction still works and gives merge_queue None, while every compose_pipeline result has a concrete MergeQueue. (paved road: Add a test that builds Pipeline(stages, merge) with two positional arguments and asserts merge_queue is None. In the same test, assert that compose_pipeline's result has isinstance(pipeline.merge_queue, MergeQueue).)
- correctness_review at tests/test_mergequeue.py: Acceptance criterion 3 is unmet. No adapter test shows that regate loads the candidate Ticket, derives the post-rebase PackingSlip from main and the candidate HEAD, and hands its Invoice to integrate by (stem, run_seq). No test shows that integration runs the ticket's Verification commands in the rebased worktree. No test shows that a red check prevents squash or that the approved SHA reaches the squash trailer. (paved road: Add concrete adapter tests against a real temporary git repo that drive pipeline.merge_queue.admit(candidate). Cover a green path, asserting the squash commit carries the reviewed SHA trailer, and a red-verification path, asserting no squash commit is made.)
- correctness_review at tests/test_mergequeue.py: Acceptance criterion 4 is unmet. No tests cover: a fresh approve pinned to the pre-rebase head integrating after main moves; a stale or missing pin being refused without squash; an up-to-date rebase succeeding when ORIG_HEAD is absent or stale; or captured head/Invoice state being cleared on success, refusal, exception and cancellation. (paved road: Add a moved-main test, an up-to-date test (delete or corrupt ORIG_HEAD first), stale-pin and missing-review refusal tests, and a cancellation test. The cancellation test should cancel an in-flight admit task. Every one of these tests should then assert that the admission_state dict passed to compose_merge_queue is empty afterward.)
