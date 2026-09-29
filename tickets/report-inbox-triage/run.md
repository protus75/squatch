## Outcome
ok

## Surprises / judgment calls
The clean retry branch lacked the earlier implementation. Restored the nine scoped files from reviewed commit 8318abfaf39648340c9f2b22d17a65985e8c5c31 after confirming its production and test predecessors matched base b76e29cd5ebb8e03b0cbd7d8e043216a42882547. Section 20 already specifies the behavior; no plan defect was found. Preserved bounded custody, host-report quarantine, arrival receipts, sequential bug authoring, and live Serve intake.

Cleared both attempt-9 findings. Inbox also redacts app_commit, app_version, each implicated_path, and replay_file. The raw replay filename is used only for locating the host file. After validating replay size, Inbox detects configured secret values through the existing Redactor and rejects secret-bearing bytes before Box custody instead of changing the replay digest. Surrogate-preserving decoding prevents invalid UTF-8 from hiding a secret. Only ReportError quarantines a report; Box OSError, ValueError, and BoxCorruption propagate with the report still available for retry. Invalid host replay paths, including embedded NULs, remain isolated as ReportError.

Regression tests reproduced both findings against the restored implementation before the fixes. Coverage includes configured secrets across metadata, a secret-bearing replay with valid or invalid UTF-8, custody failures at both Box operations, retry without losing later reports, and the live Serve worker failure/restart path.

Verification: uv run pytest tests/test_inbox.py -q exited 0 (20 passed); uv run pytest tests/test_box.py tests/test_triage.py tests/test_author.py -q exited 0 (44 passed); uv run pytest -q exited 0 (1668 passed). Additional uv run pytest tests/test_serve.py -q exited 0 (13 passed). Git diff --check passed; all committed paths are within the fence and exclude tickets/.

## Dead ends

## Second problems filed

## Resolved engine/model
OpenAI / GPT-6 (Codex).

## Predicted vs actual
75m expected; approximately 8m actual.
