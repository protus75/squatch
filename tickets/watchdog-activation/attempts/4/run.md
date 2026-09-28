## Outcome
ok

## Surprises / judgment calls
Plan status: section 20 calls for this activation; no plan change is needed. Reused the inspected implementation from prior commit 942f3a484cbae99f3b27b921b7ac6647291d361a, correcting both review findings before verification.

The Stages wrapper observes implement and review through real drain/serve construction, with filesystem mutation sampling, serving-row USD accounting, and durable run-bound signals. Notifications use the existing Effect replay/retry contract; drain reconciles at startup and after every dispatch with a private, key-stripped transport.

LLMEffect owns timeout decisions. The wrapper records stuck on an in-flight timeout abort without another elapsed-time threshold; cancellation of the Driver task still aborts without a false stuck signal. Regression coverage includes a timer 1ms under budget, the real clock/sleep pairing, actual process-group cleanup, and explicit cancellation.

ThresholdRuntime in squatch/thresh.py remains dormant and no production Stages cap wait occurs. Kept empty wait observations and left providers.py unchanged; no semaphore or new admission gate was added.

Verification, both exit 0 on the committed source contents:
- `uv run pytest tests/test_watchdog_activation.py tests/test_watchdog.py tests/test_providers.py tests/test_notify.py tests/test_serve.py tests/test_daemon_soak.py tests/test_merge.py tests/test_mergequeue.py -q`: 231 passed in 29.48s.
- `uv run pytest -q`: 1324 passed in 79.35s.

## Dead ends
Discarded the prior attempt's Registry.slot concurrency gate and fabricated competitor test: they added forbidden admission machinery and did not observe an existing production wait.

## Second problems filed
- Connect the existing ThresholdRuntime provider-concurrency admission owner to production dispatch and supply its actual wait intervals to watchdog accounting when that owner is activated. Currently thresh.py is dormant, outside this ticket's fence, and Stages has no cap wait to report.
- Activate watchdog binding for the excluded author/triage/requisition roots, standalone diagnosis, and Serve's separate Rework driver in a follow-up with their owning paths fenced and production tests. This change covers only the Stages-owned Driver on drain and serve.

## Resolved engine/model
OpenAI / GPT-6 (Codex), as identified by the session instructions.

## Predicted vs actual
Expected: 75 minutes. Actual: approximately 5 minutes, including inspection, reuse and correction of the prior implementation, both verification suites, and commit preparation.
