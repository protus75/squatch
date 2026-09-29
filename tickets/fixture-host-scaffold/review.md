---
verdict: snag
reviewed_sha: 8dc21c62ddd6acaf45414cd97db2cfada9034033
produced_by_spec_version: '1.0'
produced_at_sha: 8dc21c62ddd6acaf45414cd97db2cfada9034033
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The files stay inside the fence and the checks are green, but the fixture's regression defect cannot pass the plan's bug gate. `fixture-replay` always exits 0, and the authored `carries:` names the fix file, so running the check at the merge base can never fail on the defect.

## Findings
- correctness_review at hosts/fixture/replay.py:51: `main()` returns 0 whether or not a scenario outcome is "reproduced". SQUATCH_PLAN.md section 13 says a `kind: bug` ticket's `## Regression` command must pass at the branch head and fail at the merge base. The authored regression ticket's command, `python bin/fixture-replay --scenario report-to-regression`, exits 0 at the base where `classify('Squatch')` returns "bird". The bug gate therefore rejects the only regression scenario, so the 'one merge-base regression defect' scenario is not really delivered. The mechanical `fixture-replay` check has the same problem: it can never go red. The test only checks the JSON `actual` field, never the exit code, so the acceptance claim that the tests prove the regression is not met. (paved road: Exit nonzero when any selected scenario's outcome is "reproduced", at least for `--scenario` runs. If the full-suite mechanical check must stay green while the base defect exists, make it run a scenario that passes at the base, or give the escape case its own non-failing mode. Add a test that runs `bin/fixture-replay --scenario report-to-regression`, asserts a nonzero exit on the unfixed tree, and asserts exit 0 after the canned implement.)
- correctness_review at hosts/fixture/bin/codex:49: The authored regression ticket sets `- carries: app.py`. Section 13 says `carries:` names the branch-added test/fixture files the command needs, which the gate overlays onto the merge base. Overlaying `app.py` from the branch puts the fix itself onto the base, so the base run passes and the bug gate's 'must fail at merge base' check can never hold, even after the exit-code fix. The carried path is also not a test or fixture file the branch adds. (paved road: Have the implement step add a regression-specific test/fixture file (for example under `scenario-output/` or a dedicated `regression/` path inside the authored fence) that the Regression command reads, and name only that file in `carries:`. Never name `app.py`, the file the fix changes.)
