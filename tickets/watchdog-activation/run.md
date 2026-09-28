## Outcome
ok

## Surprises / judgment calls
The current base contained only the dormant detector; the prior attempt's implementation was not present. The plan supports this activation, so no plan defect or fence expansion was needed.

Committed 942f3a484cbae99f3b27b921b7ac6647291d361a. Drain and serve construct the watchdog around the Stages-owned CliClient. Generic LLM, Driver, LLMEffect, FakeLLM, and CliClient.call interfaces remain unchanged. Stages binds and clears ticket/run identity on every exit. Filesystem content snapshots at events, periodic observations, and call completion count committed fence edits as progress without awaiting git in an exception handler. Metered calls use reported USD as their serving-row basis; unmetered calls charge the configured estimate at the client's existing start event. Registry slots report actual cap waits; uncontended calls report none. LLMEffect remains the sole hard-timeout abort owner.

Both required commands exited 0 on the committed source contents:
- uv run pytest tests/test_watchdog_activation.py tests/test_watchdog.py tests/test_providers.py tests/test_notify.py tests/test_serve.py tests/test_daemon_soak.py tests/test_merge.py tests/test_mergequeue.py -q — 229 passed.
- uv run pytest -q — 1322 passed.

The activation tests enter main(['drain']) and main(['serve']), exercise actual Implement and Review calls, and cover soft/no-page behavior, fresh identities, committed progress, cap waits, exception preservation, notification reconciliation, private transport, and real process-group timeout cleanup. Existing serve worker/kill, provider stream/spool/redaction, merge, mergequeue, and soak tests remain green.

## Dead ends
Eager semaphore construction changed Registry validation behavior for existing synthetic API-row fixtures; lazy slot construction preserves that behavior. Reading args.verb directly broke the existing internal composition harness, which omits a CLI verb; using the root's established optional-verb lookup preserves default unbound composition. Both regressions were corrected and both required commands rerun green.

## Second problems filed
- Follow-up: bind watchdogs for requisition review, author/triage/requisition roots, standalone diagnosis, and Serve's separate Rework driver. These roots are explicitly outside this ticket's fence and were left unchanged; this entry is for the engine's run-record Suggestion Box ingestion.

## Resolved engine/model
OpenAI / GPT-6 (Codex).

## Predicted vs actual
Expected: 75 minutes. Actual: approximately 15 minutes, including implementation, regression fixes, both verification commands, and commit.
