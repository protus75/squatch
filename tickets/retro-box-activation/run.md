## Outcome
ok

## Surprises / judgment calls
Section 20 already supplies the activation contract; the missing activation and prior replay defects are implementation defects, so no plan edit was needed. The branch started at the predecessor. Reused the prior attempt's fenced activation wiring from 6f5b1f3174f56235d723cd569287542bbffd945d and corrected its rereport state handling.

Reports remain lifetime counts. The first eligible rereport of a tombstone at or above K=3 reopens it using the post-increment count, including a record first tombstoned at reports=3 or higher. A record already reopened and then tombstoned again retains its one-shot reopen marker, so the next arrival does not immediately reopen it. Successful authoring clears that marker.

A callback-free refusal persists pending_threshold_reopen explicitly. Retrying that refused operation through a journal-backed Box journals the saved threshold count without inventing another arrival. A distinct semantic incoming ID still counts as a new arrival. Normal callback failures leave the old count and tombstone intact; the journal callback precedes the single atomic replacement of count, receipt, and reopen state.

Semantic triage records the rereport before resolving the incoming message. Its incoming Box ID is persisted in the matched record's rereport_ids alongside the count, so a failure after counting but before incoming resolution can retry without double counting. Tests inject failures before journal append, after journal append, and at incoming resolution.

Status has only an event projection, not a journal writer; its read-only Box and standalone ingest remain the two explicit callback-free constructors. Drain and Serve own no direct Box constructors. All journal-backed production constructors, including both Runner sites and Merge, bind the callback. Author writes the retro bridge before Intake.commit. Merge provenance reads only the journal.

Verification passed: the exact focused command reported 266 passed; uv run pytest -q reported 1423 passed. Real inline and daemon admissions prove source/path predicates, missing/ambiguous bridge findings, the actual squash SHA, signal-before-terminal order, and replay idempotence. Merge's existing Verification/base-failure route remains covered.

## Dead ends
The first new semantic-failure tests accidentally retained assertions from the preceding test; corrected their placement. The new merge fixtures initially submitted a machine source through human intake, which correctly refused it; changed the fixtures to use Intake.commit, the existing machine-authoring entry point. Neither required a production behavior change.

## Second problems filed

## Resolved engine/model
OpenAI / GPT-6 (Codex); the exact served model variant is not exposed.

## Predicted vs actual
Expected: 75 minutes. Actual: approximately 8 minutes, including both verification commands and reuse/audit of the prior implementation.
