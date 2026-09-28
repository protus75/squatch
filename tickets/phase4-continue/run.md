## Outcome
ok

## Surprises / judgment calls
The plan already requires historical render fixtures; no plan defect or change was needed. All three reviewed ticket files are tracked on the base and were preserved unchanged. The seeded test was absent, so it was recovered from reviewed commit 236276c04a8351d37a2fb0052b3b20e372af2eac and corrected. Commit f19010dfb0b6bbaeff85570f4fa066af29225c52 contains only tests/test_seeded_phase4_01.py; nothing under tickets was committed.

Removed the live-size invariant. Historical sizes now serve only as synthetic fixtures for rendering and base-Context lint. Scanned all nine Context files at authoring and confirmed their recorded sizes and delimiter exclusion. The permanent delimiter scan covers only Context outside sibling fences, with exact Context membership pinned for every ticket. This avoids imposing future content restrictions on files that detector and activation must edit. An additional read guard confirmed the Context and headroom checks never read sibling-owned content.

Both exact verification commands exited 0: uv run pytest tests/test_seeded_phase4_01.py -q (7 passed); uv run pytest -q (1291 passed in 66.57s). The seeded suite includes lint against synthetic base Context without this admission's new files.

## Dead ends
A check-ignore probe returned no matches because the three ticket files are already tracked on this base, rather than ignored untracked outputs. No ticket changes were necessary.

## Second problems filed
None newly found. The preserved activation ticket assigns the excluded author/triage/requisition, standalone diagnosis, and separate Rework watchdog bindings to a later Suggestion Box follow-up.

## Resolved engine/model
OpenAI / GPT-6 (Codex); exact serving variant not exposed.

## Predicted vs actual
75m expected; approximately 5m actual, including verification.
