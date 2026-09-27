---
verdict: snag
reviewed_sha: 7410aedbbc22e219abfa87e80194addb9f155b69
produced_by_spec_version: '1.0'
produced_at_sha: 7410aedbbc22e219abfa87e80194addb9f155b69
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
Kill activation reaches the Stages-owned Driver abort and latches stopping before the next admission or retry draw, and the tests cover the acceptance criteria. Two things need fixing first: run_dispatch leaves the in-flight dispatch task running when the control consumer raises, and the diff deletes many docstrings, why-comments and type annotations that the ticket did not ask to change.

## Findings
- correctness_review at squatch/daemon.py:95: In DrainControl.run_dispatch, the control task finishing without `stopping` set means the consumer raised (poll_for_control/inbox.consume hit a journal or filesystem error). `await control` then re-raises straight out of the try. `active` (the runner dispatch, which already journaled `running`) is never cancelled or awaited, and `finally` only clears `self._dispatch`. The dispatch task and any Driver invocation keep running unowned in the background while the drain propagates the error and releases the lock. That breaks the 'terminal or restart-reconcilable before lock release' requirement. (paved road: On any control-task failure, cancel `active` and await it (for example `active.cancel(); await asyncio.gather(active, return_exceptions=True)`) before re-raising. Add a test in tests/test_kill_cli_activation.py where the dispatch-time control consumer raises, and assert the dispatch task has unwound before main returns.)
- correctness_review at squatch/daemon.py:1: The diff makes changes the ticket did not ask for. It deletes the module docstring and nearly every class and function docstring in squatch/daemon.py, including the DispatchPause why-comment about a pause request's identity being its release handle. It also drops the type annotation and `cast` on `DispatchAdmission._active`. In squatch/__main__.py it replaces the module docstring that documented the section 18 exit-code contract, and removes the docstrings on main, _control and _locked. In squatch/drain.py it removes the docstrings on Fold, Held, Plane, Handoff, _released, _resolve_rejects, _upgrading and _premise_road. In squatch/stages.py it removes the lift_ticket_files docstring and blank lines. None of this is needed to activate kill. (paved road: Revert every docstring, comment, annotation and whitespace change that is not required for kill activation. Keep only the DrainControl, poll/abort binding, drain stopping-latch, Stages.abort_active and CLI verb changes.)
