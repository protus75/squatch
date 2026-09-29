## Outcome
ok

## Surprises / judgment calls
The plan is sound: section 20 requires the fixture, and section 13 already requires a head-pass/base-fail regression with only branch-added tests carried. No plan or engine change was needed.
The worktree had no fixture files. Reused the prior attempt's scaffold from 8dc21c62 and corrected its behavior within the fence.
Explicit replay scenarios now exit 1 on reproduction. The default mechanical check runs the deterministic smoke scenario so the planted base defect and later deliberate escape do not prevent their intended host-loop admissions.
The bug Implement adds scenario-output/regression_check.py, and Author carries only that new test, never the fixed app. Tests overlay it onto the untouched base and assert a real classification failure.
Scripted Implement verifies and commits its canned diff through the Git seam and leaves a run record in its uncommitted outbox. Tests use real temporary Git worktrees and the engine CLI adapter, guard executable resolution before launching, and assert zero tokens and spend.
Report app_commit values are documented symbolic fixture identities for the later producer to bind to real base/squash SHAs. Escape attribution is not fabricated here.
Commit: 934ce0fbe472d4d28d17b581928195b6415065db.
Verification: uv run pytest tests/test_fixture_host.py -q passed (8 tests); uv run pytest -q passed (1628 tests).

## Dead ends
An initial read-only Python inspection command had a syntax error; corrected it before continuing. No abandoned implementation approach.

## Second problems filed
None.

## Resolved engine/model
OpenAI / GPT-6 (Codex); implement prompt spec_version=1.1.

## Predicted vs actual
Expected 75m; actual approximately 6m including focused tests, full-suite verification, and commit.
