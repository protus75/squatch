---
verdict: snag
reviewed_sha: 767f986267797f88f6914ce49d88a3cae133cf59
produced_by_spec_version: '1.0'
produced_at_sha: 767f986267797f88f6914ce49d88a3cae133cf59
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The admission boundary is sound, but the tests commit a global negative production-import assertion that the ticket explicitly forbids. They also never prove that the slot is held until completion is observed.

## Findings
- correctness_review at tests/test_daemon_admission.py:166: `test_daemon_is_unreachable_from_the_current_production_import_root` asserts that `squatch.daemon` is absent from the real `squatch/__main__.py` import closure. That is the global negative assertion the third criterion forbids. The criterion requires these tests to cover local admission behavior, not the absence of production imports, so they survive scheduler activation. The dormancy scan result belongs in the run record. As written, this test goes red the moment scheduler-activation wires the daemon in, and that ticket would have to edit an assertion owned by this ticket's fence. (paved road: Delete `test_daemon_is_unreachable_from_the_current_production_import_root`. Run the scan against the real repo root and record the result in the run record. If you keep the scan helper, test it only against the `tmp_path` fixture.)
- correctness_review at tests/test_daemon_admission.py:48: The second criterion requires proof that the active slot lasts through completion observation. No test offers a second stem while the first task is still active or finished but not yet observed and asserts that it is refused. The tests only show that an offer succeeds after `await` returns. `DispatchAdmission._release` runs as a done callback when the task finishes, and it is registered before any observer's wakeup, so the slot is freed before anyone observes the outcome. I'm uncertain whether 'observed' here means the engine's own done callback or the caller's `await`. Either way, the criterion is not demonstrated. (paved road: Add a barrier-driven test. Admit work gated on an Event and assert that a second `admit` returns `None` with zero callback calls up to the point of observation. If 'observed' means the caller's `await`, move the release so it happens in the observation path rather than a bare done callback, and assert refusal between task completion and observation.)
