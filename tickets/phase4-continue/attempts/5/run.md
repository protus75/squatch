## Outcome
ok

## Surprises / judgment calls
The starting branch was clean at 03e5f90ac511794666b186ba3ebbef6a63e7b512;
none of this admission's four output files existed. Section 20 already grants
the required identities, order, default tiers and Context/fence refinement:
these are authoring defects, not a plan defect. No plan change was needed.

Recovered the previous seeded-test contract from b5a020c, inspected its
assumptions against this base, and authored exactly watchdog-detector,
watchdog-activation and phase4-continue-02. All three start medium/medium,
cite section 20 alone and use 75m/150m budgets under the 180m ceiling.

The detector explicitly defines the empty soft band and stuck precedence,
including equal-budget and inverted-band examples, and accepts separate
filesystem mutation and provider-cap wait observations. Activation binds at
CliClient construction through an optional compose_pipeline keyword, fences
merge.py, embeds serve.py, names both predecessor dormancy assertions and
preserves the six existing composition/merge suites. Excluded LLM interfaces
and separate invocation roots remain outside that ticket's fence.

Measured all eight embedded Context lengths and five on-demand lengths on
disk; all match the historical fixtures, including providers.py at 18,687
characters. Real max-effort renders measured 44,433 (detector), 112,594
(activation) and 51,992 (continuation), each under 120,000. Each omitted
activation file independently exceeds the remaining 7,406 characters.
Historical size fixtures are not compared against future mutable files.
The seeded test scans actual Context for delimiters and exercises requisition
lint against a fixture containing only pre-existing Context, without this
admission's new test or tickets. No external model requisition review was run.

Verification: `uv run pytest tests/test_seeded_phase4_01.py -q` exited 0
(7 passed); `uv run pytest -q` exited 0 (1,291 passed, 68.50 seconds).
Only tests/test_seeded_phase4_01.py is committed to this branch. Authored
tickets and this run record remain uncommitted for engine lift, as required
by the current implement contract; the contrary prior-attempt suggestion
to commit tickets was not followed.

## Dead ends
The prior test commit contained no ticket files; an older reviewed commit
provided historical ticket text but not the corrected current contracts.
The first targeted run found criteria lacking explicit observable artifact
paths. Added the relevant test paths to those criteria; the rerun passed.

## Second problems filed
Follow-up boundary retained for activation: watchdog coverage of requisition
review, author/triage roots and Serve's separate Rework/Triage clients is
outside this admission. The activation ticket explicitly requires filing it
to the Suggestion Box rather than expanding its fence. No adjacent code was
changed and no pre-existing red test was encountered.

## Resolved engine/model
OpenAI / GPT-6 (Codex); exact serving deployment identifier not exposed.

## Predicted vs actual
Expected: 75 minutes. Actual: approximately 8 minutes, including inspection,
authoring, targeted checks and the full test suite.
