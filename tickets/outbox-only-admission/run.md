## Outcome
ok

## Surprises / judgment calls
Section 20 already specifies OUTBOX-only admission; the defect was in implementation, so no plan change was needed. This branch did not contain the earlier attempts' implementation.

Check requires a new or modified registered artifact whose exact path appears in a same-stem/run completed lift. It records those paths in its existing completion result because merge clears the OUTBOX before rebasing. Merge replays that evidence and checks foreign edits before cleanup, including both sides of renames. Unchanged reports inherited from earlier runs cannot qualify. Existing seed admission behavior is preserved, including when the seeder inherits an old report.

Verification: `uv run pytest tests/test_stages.py tests/test_merge.py -q` passed (101 tests); `uv run pytest -q` passed (1,223 tests). Only the four fenced production/test files are committed; this run record remains uncommitted.

## Dead ends
The first targeted run exposed four fixture setup errors: creating a historical report before ticket intake pre-created a directory the harness expected to create. Ordering intake before the historical report fixed the fixtures. Live worktree status alone cannot establish provenance after merge cleanup, so replay uses Check's recorded paths intersected with the completed lift.

## Second problems filed
Seed-only empty deliveries remain unsupported by the daemon integration Verification path, although merge regate recognizes seed lifts. This pre-existing source-level mismatch from the prior findings is left unchanged; it needs a separate ticket. No pre-existing red test was encountered.

## Resolved engine/model
OpenAI / GPT-6 (Codex); exact serving variant not exposed.

## Predicted vs actual
Expected 90m; actual approximately 10m, including both verification commands and regression coverage for all prior findings.
