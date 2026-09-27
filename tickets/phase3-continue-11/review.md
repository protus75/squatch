---
verdict: snag
reviewed_sha: 8ad3fd8c49101f4c9fc60ff839c2d3bb40bc6814
produced_by_spec_version: '1.0'
produced_at_sha: 8ad3fd8c49101f4c9fc60ff839c2d3bb40bc6814
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The seed tickets are correct and the checks are green. However, tests/test_seeded_phase3_11.py does not fully cover two acceptance criteria: it never checks that the authored phase3-continue-12 ticket carries its closure, Context-size and headroom obligations, and it checks new-path owners only for the activation ticket's fence.

## Findings
- correctness_review at tests/test_seeded_phase3_11.py:140: Acceptance criterion 4 asks the test to pin the heartbeat Context-size/headroom requirements and the predecessor-test closure requirement inside the authored phase3-continue-12 ticket. test_continuation_repairs_heartbeat_ownership_and_context_contract checks only the ownership, new_path_owners and admissions YAML plus Context equality. It never reads phase3-continue-12's `## Scope in` or `## Acceptance criteria` text. Someone could delete the obligation that tests/test_seeded_phase3_12.py pins authoring-time Context sizes, max-effort headroom, predecessor-test closure, and 'every existing fence path is existing Context', and this test would still pass. test_authoring_sizes_and_max_effort_headroom renders the ticket only now; it does not pin that the successor must repeat the check. The predecessor test_seeded_phase3_10.py does pin its successor's obligations in both sections. (paved road: Follow the phase3_10 pattern. For both `Scope in` and `Acceptance criteria` of phase3-continue-12, assert that the section names the daemon preservation tests (tests/test_daemon_tasks.py, tests/test_control_cli.py, tests/test_daemon_composition.py). Also assert that the Acceptance criteria text requires authoring-time Context sizes, max-effort headroom, predecessor-test closure, and existing-fence-path-is-Context.)
- correctness_review at tests/test_seeded_phase3_11.py:125: Acceptance criterion 1 asks for the new-path owners to be pinned. NEW_PATH_OWNERS is checked only against kill-cli-activation's fence. phase3-continue-12's new fence path tests/test_seeded_phase3_12.py never gets its owner asserted, and nothing checks that each fence path is either existing Context or an owned new path. So a phase3-continue-12 fence entry that is neither would go unnoticed. (paved road: Put the fence-classification loop in test_exact_seeds_edges_tiers_budgets_cap_and_fences, or loop it over every stem in BATCH. For each fence path, assert one of: it is a new path whose NEW_PATH_OWNERS entry equals the stem; it is the `tickets` directory; it is an ON_DEMAND path (activation only); or it is in ticket.context.)
