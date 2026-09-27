## Outcome
ok

## Surprises / judgment calls
The `serve-merge-admission` prerequisite is now present: `Serve.compose` selects daemon admission, and settled deliveries reach `Merge.admit_daemon` and the composed `MergeQueue`. The runner uses three isolated local repositories so every report entry has its own journal, Box, and run identity. A matching Box record yields disposition `box`; otherwise an applied kill plus reconciled abandonment, or the run's production escalation signal, yields `alert`.

The conflict member advances main during the scripted Implement provider call and lets the normal Check and Review stages finish before production admission. The semantic member fails only the third verification invocation: initial Check and post-rebase regate are green, while the queue's integration verification is red. Review approval is returned only through the scripted provider process and is lifted by the production Review stage.

## Dead ends
The prior approach called `MergeQueue.admit` from inside the Implement provider and wrote `review.md` from the harness. Both were removed. Report derivation also now constructs `Box` with the member's injected filesystem and clock rather than a fresh local filesystem and wall clock.

Verification completed on commit 84076c048a6c28ab244751238745bcaf8b867019: `uv run pytest tests/test_daemon_soak_runner.py -q` (2 passed), `uv run pytest tests/test_daemon_soak.py -q` (5 passed), and `uv run pytest -q` (1182 passed).

## Second problems filed
None.

## Resolved engine/model
OpenAI / Codex; exact serving model variant not exposed.

## Predicted vs actual
Expected: 75 minutes. Actual: approximately 35 minutes, including prerequisite/path inspection, prior-attempt repair, and full verification.
