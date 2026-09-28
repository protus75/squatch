## Outcome
ok

## Surprises / judgment calls
Section 20 supports this admission without a plan change. Authored exactly
watchdog-detector, watchdog-activation and phase4-continue-02, all confirmed
medium/medium, with the exact dependency chain and shrinking registry.
Activation binds at CliClient construction for the Stages-owned Driver on
drain and serve, review included; LLM/FakeLLM/LLMEffect signatures stay fixed.
The separate rework Driver and author/triage/requisition roots are excluded.
The existing timer test is tests/test_restart_timers.py.

All seven historical Context lengths were measured and independently checked
against base da21cb79fb29532abf10e9a836ff2d6497c84686. In particular,
squatch/providers.py is 18687 characters; tests/test_providers.py is 32667.
Historical fixtures intentionally do not assert future live lengths because
the emitted tickets must edit these files. Context content is scanned for
delimiters, including files beyond the explicit squatch/specs.py exclusion.

Requisition's lint_ticket boundary passed for all three tickets using only
base-commit Context copied into an isolated temporary tree, with co-admitted
dependencies resolved explicitly. No newly authored file was available as
Context. Actual max-effort renders measured 44056, 100122 and 51645 characters
respectively, each below REQ_RENDER_HEADROOM's 120000-character limit.

Verification: uv run pytest tests/test_seeded_phase4_01.py -q exited 0
(7 passed); uv run pytest -q exited 0 (1291 passed, 70.03 seconds).
Only tests/test_seeded_phase4_01.py is committed. The three authored tickets
and this run record remain uncommitted for engine lift, following the current
spec's explicit prohibition on tickets/** branch commits; the prior-attempt
suggestion to commit them was not followed.

## Dead ends
Initial seeded verification caught missing backtick quoting around observable
artifact paths in the new tickets and a nonexistent tests/test_timers.py path.
Quoted the paths and used the existing tests/test_restart_timers.py suite;
both required Verification commands then passed.

## Second problems filed
- Watchdog coverage for squatch/author.py, squatch/triage.py, squatch/requisition.py and Serve.compose's separate rework Driver needs a follow-up with its own ownership and production proofs. This admission activates only the Stages-owned Driver on drain and serve; the excluded roots remain unchanged.

## Resolved engine/model
OpenAI / GPT-6; exact serving variant not exposed.

## Predicted vs actual
Expected: 75 minutes. Actual: approximately 8 minutes, including verification.
