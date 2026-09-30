---
verdict: snag
reviewed_sha: 03363db3ad22556078fd6a019689ad1efa9dab6c
produced_by_spec_version: '1.0'
produced_at_sha: 03363db3ad22556078fd6a019689ad1efa9dab6c
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The receipt, the digest, the incomplete-grade NO_GO mapping, the identity mapping, the fence and the no-successor checks are all correctly exercised, and the check report is green. One acceptance clause is unmet: nothing ties the committed host-loop report to the registered fixture host, so the test does not show that fabricated or live-host evidence would be rejected.

## Findings
- correctness_review at tests/test_phase6_exit.py:107: Acceptance requires the test to prove that forbidden live-host inputs are rejected, and the Definition of rejected names fabricated or unregistered evidence. The only live-host guard is in test_terminal_fence_has_no_engine_edit_successor_or_external_evidence_input: a static scan of the test's own source for a journal import and a `.squatch/state` string. That constrains the test file, not the evidence. test_exit_serialized_registered_artifacts_and_exact_digest only checks the committed host-loop-report.json for schema validity, member order and three distinct runs. test_registered_producer_returns_closed_fixture_host_report runs the fixture `run()` but never compares its result with the committed file. A hand-written report, or one from a live host, with the right member shape would pass every assertion. (I am somewhat unsure how strict this criterion is meant to be, but as written no test enforces it.) (paved road: Bind the committed OUTBOX report to the registered fixture producer. In the digest test, assert that the committed entries' (member, scenario) pairs and producing_run stems equal those of the report returned by `host_loop.run()` in the producer test, or at least that every entry's stem is drawn from `host_loop.STEMS` / `host_loop.INITIAL_SCENARIOS`. Share one run through a module-scoped fixture so `run()` executes once. Add a negative case: a report whose scenarios or producing_run stems fall outside the fixture registry must be rejected by that same check.)
