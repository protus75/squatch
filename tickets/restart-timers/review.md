---
verdict: snag
reviewed_sha: 54f65ab898a4f09fc016eb84e27e14fae067be66
produced_by_spec_version: '1.0'
produced_at_sha: 54f65ab898a4f09fc016eb84e27e14fae067be66
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
Timers are journaled, re-armed once from a fold, and wired into the lock-held Runner session. The Restart composition is never wired into the production daemon, so the first acceptance criterion is only proven against a composition the daemon never builds.

## Findings
- correctness_review at squatch/daemon.py:194: `compose_daemon_dispatch(..., restart=...)` and `compose_daemon_restart` are only reached from tests. The one production call site (`squatch/__main__.py` factory, `graph = compose_daemon_dispatch(config_supplier, work, pause=pause, wait_for_control=wait_for_control)`) passes no `restart`, and nothing in `__main__.py` calls `compose_daemon_restart`. In production, reap-before-dispatch still happens only because `Runner.session` calls `reconcile` directly. `tests/test_restart_timers.py::test_restart_delegates_to_existing_reconcile_once_before_dispatch` builds its own graph with a fake reaper, so it proves ordering on a path the daemon never runs. The result is a dead second entry point to `reconcile`, and wiring it as written would reap twice per session. That breaks both 'restart composition delegates ... before any dispatch offer' for the real daemon and the ticket's 'no second reap path'. I am unsure whether the ticket intends Restart to replace the Runner call, which is out of fence in `runner.py`, or only to wrap it. If it cannot be done inside the fence, this is an rma on the ticket's premise. (paved road: Make the proof cover the composition production actually uses. One option: in `__main__.py`, bind `compose_daemon_restart(...)` into the factory's `compose_daemon_dispatch` call so it becomes the single pre-dispatch reap. Then show in the test, through `main_module.main`, that `reconcile` runs exactly once before the first dispatch offer. The other option: drop the unused `restart` parameter and hook, and have the test assert through `main_module.main` that the existing `Runner.session` reconcile precedes the dispatch offer. If neither fits the fence without editing `squatch/runner.py`, stop under the ticket's Definition of rejected and return it for re-scoping.)
