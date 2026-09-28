## Outcome
ok

## Surprises / judgment calls
Section 20 supports this admission without a plan change. The branch lacked all four deliverables. Recovered the previous seeded test from commit 10319c888e1da70ea8fe4ebae8f6226e2c900029 and re-authored the three absent tickets with the reported corrections: medium/medium tiers, USD detector accounting, wrapper binding, explicit notification reconciliation, dormancy migration, and the exact finite suffix. Added base-Context requisition lint and successor ownership checks. The current spec explicitly forbids committing tickets; it takes precedence over prior-attempt advice to commit them. Commit 236276c04a8351d37a2fb0052b3b20e372af2eac contains only tests/test_seeded_phase4_01.py; all three authored tickets remain available for engine lift.

Both exact verification commands exited 0: uv run pytest tests/test_seeded_phase4_01.py -q (7 passed); uv run pytest -q (1291 passed in 69.74s). Lint succeeds against a fixture without this admission's created files. Measured actual max-effort renders: detector 95674, activation 88434, continuation 51911 characters, each below 120000.

## Dead ends
The previous commit did not contain authored ticket files, so they could not be restored from that commit. A path probe found no tests/test_timers.py; the existing timer predecessor is tests/test_restart_timers.py, which the continuation now names.

## Second problems filed
The activation ticket explicitly leaves watchdog coverage for author/triage/requisition, standalone diagnosis, and the separate Rework driver to Suggestion Box follow-up. No adjacent implementation was changed. The prior malformed reviewer reply was not reproduced or worked around; its truncated contents do not establish a ticket defect.

## Resolved engine/model
OpenAI / GPT-6 (Codex); exact serving variant not exposed.

## Predicted vs actual
75m expected; approximately 12m actual, including verification.
