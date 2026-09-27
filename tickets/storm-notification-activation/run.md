## Outcome
ok

## Surprises / judgment calls
The starting branch contained the dormant implementation. Reused the eight fenced files from prior implementation bfe1906eff253e2d22d2603c0b2c7a19b1bb2344 after inspecting its diff against the ticket and plan section 20. The plan is sound; the outstanding lock-acquisition error handling is an implementation defect. Added an OSError refusal around acquire and a real invalid-state-directory regression test; release remains reachable only after successful acquisition.

Acceptance coverage in tests/test_storm_notification_activation.py:
- test_main_run_binds_preconstructed_boxes_for_harvest_and_verification_paths covers real run composition, preconstructed Boxes, second-problem and verification-attribution enqueue, lock ownership, timer shutdown and binding reset.
- test_main_run_exception_unwinds_binding_timer_and_lock covers exceptional cleanup.
- test_crossing_rule_boundaries_and_trip_identity_are_replay_stable covers threshold, expiry, repeat and fresh crossings, canonical identity and None stage.
- test_rolled_occurrence_recovery_reuses_resolved_report_without_recursion covers occurrence-before-trip recovery from rolled segments, resolved reports, repeat replay and recursion exclusion.
- test_trip_before_report_crash_repairs_exactly_one_report covers signal-before-report repair without report-count inflation.
- test_unbound_enqueue_writes_no_journal_and_cli_ingest_refuses_the_live_lock covers unbound arrivals and lock refusal without Box mutation.
- test_cli_ingest_refuses_invalid_state_directory_with_paved_road covers the outstanding review finding with exit 2 and actionable diagnostics.
- test_real_drain_dispatches_after_trip_without_a_storm_control_hold preserves the dispatch-absence assertion for the next seed.

All required commands exited 0:
- uv run pytest tests/test_storm_notification_activation.py tests/test_storm_producer.py tests/test_storm.py tests/test_box.py tests/test_daemon_composition.py -q — 38 passed.
- uv run pytest tests/test_drain.py::test_bootstrap_drain_never_scans_or_mutates_the_box -q — 1 passed.
- uv run pytest -q — 1131 passed in 49.44s; observed final exit status 0.

Ledger/producer positives and the drain no-mutation/no-triage assertions remain. tests/test_box.py and tests/test_daemon_composition.py are unchanged.

## Dead ends
None.

## Second problems filed
None.

## Resolved engine/model
OpenAI Codex, GPT-6 (exact serving variant unavailable).

## Predicted vs actual
Expected 75 minutes; actual approximately 5 minutes, including reuse inspection, regression fix, verification and commit.
