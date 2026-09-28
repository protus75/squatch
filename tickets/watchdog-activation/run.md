## Outcome
ok

## Surprises / judgment calls
Plan status: section 20 calls for this activation; no plan defect or plan edit was needed. Inspected and reused the scoped activation from prior commit 51063787ca9dc5dbd0d45674cd7918d3409851da, then corrected its mutation-sampling finding.

Drain and serve construct the Stages watchdog before work begins. Implement and review share the run-bound observer; every exit clears the binding. Serving-row USD accounting, replay-safe soft/stuck identities, private key-stripped notification transport, and drain startup/per-dispatch reconciliation are preserved. LLMEffect remains the only hard-timeout owner; soft trips never abort.

Filesystem has no metadata/stat operation. Following the review's Git-seam alternative, observation now compares asynchronous worktree status and HEAD changes, including committed and untracked output paths. Sampling occurs at worktree binding, call exit, and a 10-second injected Sleep interval. Stream callbacks perform no observation I/O. Git observation failures cannot replace the provider's original error. Repeated unchanged dirty status does not repeatedly reset spend.

The directory-fence regression drives main(['drain']) and main(['serve']) with 1,024 files (about 9 MiB), thousands of streamed events, and committed plus filesystem-seam untracked mutations. It proves zero observation I/O per callback and mutation detection both at the timer tick and at the call boundary. Existing healthy/soft/fresh-run, notification replay/retry, early/real deadline, process-group cleanup, and explicit cancellation proofs remain green.

Verification, both exit 0 on the source contents committed for this attempt:
- `uv run pytest tests/test_watchdog_activation.py tests/test_watchdog.py tests/test_providers.py tests/test_notify.py tests/test_serve.py tests/test_daemon_soak.py tests/test_merge.py tests/test_mergequeue.py -q`: 235 passed in 36.99s.
- `uv run pytest -q`: 1328 passed in 85.58s.

The scope audit and git diff whitespace check passed. CliClient.call, FakeLLM, the generic LLM/Driver/LLMEffect interfaces, provider behavior, merge admission behavior, and preservation suites remain unchanged.

## Dead ends
The first directory regression incorrectly asserted zero filesystem I/O across the entire CLI run, counting unrelated control-inbox reads and walks. Corrected the counter to distinguish fenced-output I/O, while retaining the strict no-I/O assertion around every stream callback. The initial required suite had four new-test failures; all passed after that test correction.

Discarded recursive content hashing and per-event sampling from the prior implementation. The existing filesystem seam cannot supply cheap metadata, so the supported asynchronous Git seam supplies status/HEAD observations without expanding the fence.

## Second problems filed
- Suggestion Box follow-up: bind watchdogs for the excluded author/triage/requisition roots, standalone diagnosis, and Serve's separate Rework driver, with their owning paths fenced and production-path tests.
- Suggestion Box follow-up: connect the dormant ThresholdRuntime provider-concurrency admission owner to production and supply its actual wait intervals to watchdog accounting when activated. Stages currently has no provider-cap wait, so its wait observations are empty; no semaphore or new admission gate was added here.

## Resolved engine/model
OpenAI / GPT-6 (Codex), as identified by the session instructions.

## Predicted vs actual
Expected: 75 minutes. Actual: approximately 10 minutes, including plan/context inspection, reuse and correction of the prior activation, directory regression tests, both verification suites, and commit preparation.
