## Outcome
ok

## Surprises / judgment calls
The worktree contained the dormant predecessor boundary. Inspected and reused the seven scoped activation files from 69c97ab7d8ce7b22de351b17b06a2aaa764dea93, then fixed the remaining lock-identity finding. Section 20 already requires identity-bound control and a single journal writer; this was an implementation defect, not a plan defect.

The production control factory reads the actual Holder record through the filesystem seam after Runner has acquired its lock and exposed the journal. This avoids changing the unfenced Runner/Lockfile APIs or guessing the acquisition timestamp in advance. Lifecycle signals store that Holder, and live CLI publication requires an exact match, including pid and started_at. Regression cases retain the engine version while independently changing each acquisition field; both refuse without publishing or journaling. Existing live publication remains covered with matching identity.

Retained production drain routing, durable no-engine pause/resume, decision-before-mutation, accepted-but-unapplied crash recovery, matching release, non-preemption, accounting-order tests, and the injectable one-second control wait. Merge admission holds remain the dependent ticket's boundary.

Verification commands ran exactly as specified and exited 0:
- uv run pytest tests/test_control_cli.py tests/test_daemon_pause.py tests/test_daemon_composition.py tests/test_daemon_tasks.py tests/test_control.py tests/test_drain.py -q: 115 passed in 8.94s.
- uv run pytest -q: 1020 passed in 45.81s.

Preservation-only suites are unchanged. The commit contains only the seven fenced code/test paths; this run record is uncommitted.

## Dead ends
None.

## Second problems filed
None.

## Resolved engine/model
OpenAI / GPT-6 (Codex); exact serving variant unavailable.

## Predicted vs actual
Expected: 75 minutes. Actual: approximately 7 minutes, including inspection, prior implementation recovery, identity fix, verification, and commit.
