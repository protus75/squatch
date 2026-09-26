## Outcome
ok

## Surprises / judgment calls
The clean base 3088f1e63f79de80520a8157d9cbd9217019b219 had no control inbox implementation. Read and reused the six fenced files from prior commit bb23506fbed3370a978032202c92dec4c41f7db1, whose existing hook files matched this base, then fixed its reproduced terminal-decision replay defect. Section 20 already specifies the required behavior and authorizes the filesystem seam; no plan defect or change was needed.

Filename/request_id mismatches now compare the recorded invalid decision before appending. The replay audit also reproduced duplicate refusals for a payload missing request_id, because model defaults minted a fresh identity on every read; consumption now rejects that missing wire identity as a stable, digest-bound invalid decision. Publishing still mints request IDs during request construction.

Regressions inject two consecutive removal crashes for malformed payloads, filename mismatches, missing wire IDs, all three stale reasons, and conflicts following accepted/stale/invalid/conflict decisions. They assert one terminal decision, no extra mutation, unchanged holds where applicable, and eventual removal. Invalid and stale cases close and reopen the Journal between retries.

State machine: published -> accepted decision -> mutation -> applied marker -> removed; refusals are journaled before removal without mutation. A restart mints a new lifecycle and terminates incomplete prior acceptance as stale. Completed requests never mutate again. Preserved the explicitly tested callback-to-applied-marker failure window: a same-lifecycle retry can call twice there and requires callback idempotency keyed by request_id, since journal append and the external callback cannot commit atomically. Other completion/republication crash tests assert one callback call.

Committed 75325c29a103c0dcd422940e5f7988e71402313f on control-inbox, containing only the six fenced implementation/test files. tests/test_daemon_composition.py is unchanged; no tickets were committed. No CLI verbs were activated and task-consumer policy is unchanged.

Verification commands executed exactly as specified:

- uv run pytest tests/test_control.py tests/test_daemon_tasks.py tests/test_daemon_composition.py tests/test_seams.py -q: exit 0, 61 passed in 4.43s.
- uv run pytest -q: exit 0, 992 passed in 45.02s.

## Dead ends
None. The new filename-mismatch and missing-request-id regressions failed against the restored prior implementation before the fix, confirming both replay defects; the conflict and stale audit cases already passed.

## Second problems filed
None.

## Resolved engine/model
OpenAI / GPT-6-based Codex, as identified by the session instructions; exact serving model identifier is not exposed.

## Predicted vs actual
Expected: 75 minutes. Actual: approximately 6 minutes, including inspection, regression reproduction, both verification commands, commit, and run record.
