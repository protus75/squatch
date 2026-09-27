---
verdict: snag
reviewed_sha: 6b8a9ee8059bcefafa42eaf65416bf9f5fba11ad
produced_by_spec_version: '1.0'
produced_at_sha: 6b8a9ee8059bcefafa42eaf65416bf9f5fba11ad
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The seam, adapter and kwargs-gating code looks correct and stays inside the scope fence. Acceptance criterion 2 is only partly proven: the tests cover one of the three Codex tool-call shapes, never feed non-JSON chatter, and never check redaction or spool capture while a consumer is supplied.

## Findings
- correctness_review at tests/test_providers.py:393: Criterion 2 asks the tests to prove normalized events for the supported JSONL tool-call shapes. CodexAdapter._watchdog_events accepts three item types: command_execution, file_change and mcp_tool_call. Only command_execution is exercised (test_codex_watchdog_starts_with_its_flat_estimate_and_normalizes_tools). Nothing tests that file_change or mcp_tool_call produce a tool_call event, or that other item types and non-item.started events produce none. The one extra line tried is an item.completed line, which covers only part of that negative case. (paved road: Parametrize the Codex watchdog test over all three accepted item types. Add at least one rejected item type and one non-item.started event, and assert that each yields exactly the expected events.)
- correctness_review at tests/test_providers.py:383: Criterion 2 also asks the tests to prove the event stream changes neither redaction nor spool capture, and the Scope-in says non-JSON chatter is ignored for events but stays in the returned capture. No test combines a supplied on_event consumer with (a) a non-JSON chatter line, (b) a configured secret in the stream, or (c) the spooled or returned capture. The consumer tests only assert result.text, result.usd and the collected events, so the redaction/spool half of the criterion and the chatter rule are unproven. (paved road: Add a provider test that supplies an EventCollector and a stream containing a non-JSON chatter line and a configured secret value. Assert that the chatter produces no event, that the returned and spooled capture keep the chatter with the secret redacted, and that the result matches the same call made without a consumer.)
