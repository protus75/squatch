## Outcome

ok

## Surprises / judgment calls

The plan already specifies the required behavior; no plan defect or fence expansion was needed. Reused the inspected prior-attempt implementation, then corrected the remaining credential leak and wrapper bypass. Doctor runs its version probe through the existing Git._run argv wrapper with child_env filtering configured auth names. If config cannot load, its child inherits only PATH. No git.py change or second executor was introduced.

Manual retro shares _compose_retro and the provider/timer session composition with drain. Its separate lock-held entry checks the window before opening a journal writer and skips ticket intake/reconciliation. The no-merge snapshot test permits only the mandatory lock record; all other files remain unchanged. The shared doctor lock probe accepts brief contention with a racing writer to avoid trusting a stale record. Venv identity uses sys.prefix, with a real executable-symlink regression test.

Acceptance evidence:
- tests/test_doctor.py: test_doctor_runs_the_five_ordered_read_checks_and_renders_exactly, test_doctor_bounds_each_exception_and_checks_everything, test_probe_exception_does_not_skip_later_checks, test_real_lock_probe_is_read_only_for_missing_free_and_live_lock, test_default_journal_reader_checks_active_and_rolled_records_without_writing, and test_git_probe_never_inherits_provider_credentials cover ordering, exact rendering, bounded failures, read-only probes, 0/2 exits, and both credential-filtering cases.
- tests/test_retro.py: test_manual_retro_without_a_merge_prints_the_quiescent_operator_result, test_manual_retro_commits_through_the_governed_retro_path, test_manual_retro_selected_model_failure_is_exit_one_and_commits_no_report, test_manual_retro_prior_git_suppression_is_not_this_runs_refusal, and test_manual_retro_git_failure_retains_refusal_rendering_and_exit_two prove no-merge, success, selected failure, suppression, and Git refusal. The production provider-payload test now exercises both drain and retro.
- tests/test_cli.py covers parser help, held-lock refusals, exact doctor and retro output, exit classes, config/construction/Git/journal refusals, plus construction exceptions and journal I/O failure.
- tests/test_verbs.py covers the registered surface, provider/pipeline-free doctor dispatch beside a live lock holder, and manual forced retro dispatch under the writer lock through the shared Driver.

Committed 7ea945040facaf30bcf5fc1ff70c1e3b7a8e7fb8. Both exact verification commands passed on the committed tree:
- uv run pytest tests/test_doctor.py tests/test_retro.py tests/test_cli.py tests/test_verbs.py -q: 85 passed.
- uv run pytest -q: 1490 passed.

## Dead ends

The first new credential test omitted required config fields; corrected its fixture. The construction-failure test initially used a helper that wraps pipeline objects rather than invoking a factory; changed it to call main directly. A full-suite run already in flight retained that old test and failed; the final committed-tree rerun passed all 1490 tests.

## Second problems filed

None.

## Resolved engine/model

OpenAI / Codex, GPT-6 family as identified by the session instructions; exact served model identifier is not exposed.

## Predicted vs actual

Expected: 75m. Actual: approximately 9m, including inspection of the earlier attempt and final verification.
