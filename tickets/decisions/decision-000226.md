---
id: decision-000226
kind: decision
link: box-000226-28e7dd61
reopen_after_days: 90
message: box-000226-28e7dd61
---
No ticket. The work this message wants to steer has already happened. The diagnosis-eval seeds ran and merged on main. eval/diagnose.py defines `DiagnosisEvalReport` (:202) along with its `--report` writer and `--check` validator (:438). The run seed tickets/diagnosis-eval-run/ticket.md set the path to `eval/reports/diagnosis-eval.json` and committed it there (commit b30e485). Its review records 12/12 fixtures scored with `stopped` null. So the report has one writer and one committed path. The consumers the message expects do not read that path. go-grade-machinery, go-grade-run and phase6-exit have all merged, and nothing in squatch/, eval/ or tests/ refers to `eval/reports/diagnosis-eval.json`. The ladder lives in squatch/ladder.py and is driven by the journal, so it reads no eval report either. Adding the path to section 19 now would describe a bootstrap step that is already finished, and no reader needs it. Section 17 calls that history, not spec. Under D10 it would also be speculative: the message gives no evidence and comes from `bootstrap-ingest`. A tombstone does not fit. diagnosis-eval-run is the stem that owns the artifact, but it does not appear in the rendered merged_work projection, so it cannot be linked.

Evidence: eval/diagnose.py:202 (`DiagnosisEvalReport`), :438 (`--check` validation); tickets/diagnosis-eval-run/ticket.md:23,29,38-45 set and validate `eval/reports/diagnosis-eval.json`; eval/reports/diagnosis-eval.json is committed (b30e485); grep finds no reader of that path in squatch/, eval/ or tests/; SQUATCH_PLAN.md:723 names only a 'committed report artifact'. Reopen if a regeneration of the diagnosis-eval seeds is planned, if any ticket or code is authored to read the diagnosis-eval report, or if `eval/reports/diagnosis-eval.json` moves or is removed from main.
