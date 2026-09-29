## Outcome
ok

## Surprises / judgment calls
The clean retry branch did not contain the earlier implementation; restored its nine scoped files from retained commit 62298b037750a907f6a543365862e1380c65e457. Section 20 already specifies the required behavior, so this is an implementation correction rather than a plan defect. Arrival receipts hash the filename plus report bytes, preserving distinct same-content submissions while making crash retries idempotent. Box persists the initial receipt with the message and uses its existing rereport receipt mechanism thereafter. Added restart tests for failed filed-renames after both enqueue and a genuine rereport, including tombstone threshold preservation, and a negative Author evidence-retention test.

Verification: `uv run pytest tests/test_inbox.py -q` exited 0 (8 passed); `uv run pytest tests/test_box.py tests/test_triage.py tests/test_author.py -q` exited 0 (44 passed); `uv run pytest -q` exited 0 (1653 passed).

## Dead ends

## Second problems filed

## Resolved engine/model
OpenAI / GPT-6 (Codex).

## Predicted vs actual
75m expected; approximately 6m actual.
