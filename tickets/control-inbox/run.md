## Outcome
ok

## Surprises / judgment calls
The base had no control inbox implementation. Reused the six fenced files from prior commit e213ec822fd6a0d4a654bd8c3dc20f39cab0ec72 and fixed its reproduced terminal-decision bypass. The plan already specifies the required behavior; this was an implementation defect, so no plan change was needed.

Every file is now read and validated before a previous terminal decision can be reused. Different valid content under an already-decided ID journals conflict for accepted, stale, invalid, and conflict predecessors. Invalid payloads carry a digest so identical malformed replay is deduplicated while different malformed bytes receive a new invalid decision. Regressions assert the journal record, zero mutation calls, unchanged holds, removal, and identical replay.

State machine: published -> accepted decision -> mutation -> applied marker -> removed; refusals are journaled before removal without mutation. A restarted engine has a fresh lifecycle and journals an incomplete prior acceptance stale. Completed requests do not mutate again. Preserved the explicitly tested callback-to-applied-marker failure window: same-lifecycle retry can call twice there, requiring request_id idempotency from the callback; the journal and callback cannot commit atomically. Other completion/republication crash tests assert one callback call.

Committed bb23506fbed3370a978032202c92dec4c41f7db1, containing only the six fenced implementation/test files. tests/test_daemon_composition.py is unchanged; no tickets were committed.

Verification commands executed exactly as specified:
- uv run pytest tests/test_control.py tests/test_daemon_tasks.py tests/test_daemon_composition.py tests/test_seams.py -q: exit 0, 51 passed.
- uv run pytest -q: exit 0, 982 passed.

## Dead ends
The new stale/invalid/conflict regression cases failed against the restored prior implementation, confirming the finding before the fix. The initial commit invocation omitted HOME from its child environment and could not resolve the configured author identity; including HOME allowed the commit without changing git configuration.

## Second problems filed
None.

## Resolved engine/model
OpenAI / GPT-6-based Codex, as identified by the session instructions; exact serving model identifier is not exposed.

## Predicted vs actual
Expected: 75 minutes. Actual: approximately 4 minutes, including verification and commit.
