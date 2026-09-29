---
verdict: snag
reviewed_sha: 884dfa6cad00c3888082103d5fe7fa524ad1a907
produced_by_spec_version: '1.0'
produced_at_sha: 884dfa6cad00c3888082103d5fe7fa524ad1a907
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diff adds the three fields and the scorecard wiring (injected clock, HEAD from Git.rev_parse, the real retro spec version), and checks are green. One fold is wrong: `merged` uses the latest transition of any kind, but the ticket asks for the latest terminal transition, and no test tells the two apart.

## Findings
- correctness_review at squatch/status.py:83: Scope in (and plan section 20) says `merged` is the stems whose latest TERMINAL transition is `merged`. The new code, `merged = {stem for stem, record in latest.items() if record.get("to") == "merged"}`, uses `latest`, which holds the latest transition of ANY kind, including the non-terminal `running`. So a journal of `merged` then a later `running` for the same stem drops that stem from `merged`, lists it as in_flight, and makes every dependent `blocked`. The spec keeps it merged. The test in tests/test_status.py only has running->merged, so it cannot catch this, and acceptance criterion 1 ('all deterministic folds') is not really proven for `merged`. I am not sure a running-after-merged journal can happen in production, but the code does not do what the ticket says. (paved road: Keep a separate per-stem latest terminal transition, updated only when `body['to']` is in TERMINAL_RUN_STATES, and derive `merged` from it. Add a test_status.py case with a stem journaled merged then running (expect it in `merged`, not in `in_flight`) and a stem journaled merged then a later terminal non-merged state (expect it not in `merged`).)
