---
verdict: snag
reviewed_sha: a4d8dcc91783a227ada734bc6b656f22d1fba351
produced_by_spec_version: '1.0'
produced_at_sha: a4d8dcc91783a227ada734bc6b656f22d1fba351
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
Both test files stay inside the fence, cover the criteria, and pass the check report. But test_phase5_exit.py picks the retro report by 'latest at HEAD' and pins it to a literal, so the next drain-produced retro will turn the whole suite red for every Phase 6 ticket.

## Findings
- correctness_review at tests/test_phase5_exit.py:66: test_latest_committed_forced_report_closes_the_phase5_window selects `reports[-1]` from `git ls-files` at HEAD. It then asserts that the report is `tickets/retro/000010.md` and that its trigger is `phase-exit`. The drain keeps committing retro reports: retro-drain-invoker fires on `quiescence` as well as `phase-exit`, and 000001-000009 already exist. Once Phase 6 construction commits `tickets/retro/000011.md`, this test fails in `uv run pytest -q`. Every later Phase 6 ticket then fails its verification gate on red it inherited, and the drain stalls. The test also never proves that the report was committed after the latest Phase 5 feature merge, as the Scope-in requires. It only checks that the text mentions `phase5-continue-04`, which is a textual proxy and not commit ordering. (paved road: Bound the selection to the Phase 5 window from committed history instead of HEAD. For example, pick the lexicographically latest `tickets/retro/[0-9]{6}.md` whose adding commit (found through git.py log or rev-list) comes after the merge commits of the named Phase 5 stems and at or before the phase5-exit ticket commit. Assert that ordering explicitly. Then drop the hardcoded `000010` literal, so later quiescence or Phase 6 retro reports cannot break the proof.)
