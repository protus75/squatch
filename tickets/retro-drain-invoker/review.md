---
verdict: snag
reviewed_sha: 2fa85e7c1ae7db814607421c991096c5052c1899
produced_by_spec_version: '1.0'
produced_at_sha: 2fa85e7c1ae7db814607421c991096c5052c1899
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The retro module, window folding, failure suppression and Drain hook points look sound. But no test proves that `_drain` binds the hook, that a self-upgraded child rebinds it, or that the writer lock is held, and the production binding contains a silent no-op path. That path is the likely reason the ticket's expected post-merge retro changes never show up in any of the named regression suites.

## Findings
- correctness_review at tests/test_retro.py:253: Acceptance criterion 2 is only partly met. The only hook test builds `Drain` directly with a stub `retro_factory`. No test calls `squatch.__main__._drain` or `main(["drain"])` to show that the production hook is bound, that a self-upgraded CLI child rebinds it, or that the report commit happens while the drain's writer lock is held. Direct-write, zero-padding and effect-key coverage exist, but only through a hand-built `Retro`, never through the `_drain` binding. (paved road: Add tests to `tests/test_retro.py` that run `main(["drain"], ...)` with a real-shaped scripted pipeline (like `Real` in `tests/test_drain_reentry.py`). Assert that a merge followed by quiescence produces exactly one `tickets/retro/000001.md` commit on main, keyed by effect `retro/000001`, with the lockfile held during the commit. Also assert that a self-upgrade handoff child running `_drain` gets a bound hook.)
- correctness_review at squatch/__main__.py:200: In `retro_factory`, if `getattr(getattr(composed, 'stages', None), '_driver', None)` is None, the hook returns False with no signal, no Box message and no log entry. A due or forced retro is then skipped silently every iteration, which fails open. This probably also explains why none of the named regression suites needed their listed changes: the ticket expects one forced post-merge retro to change scripted-answer counts, main history, Box counts and journal sequences in those suites, yet the diff touches none of them. So either the retro never fires on those production-shaped paths, or it fires and then fails invisibly. I could not run the suites to confirm which, so this is uncertain. (paved road: Get the driver through an explicit public accessor on the composed pipeline or `Stages`, not private-attribute probing. Treat a missing driver as a construction error, not a silent False. Then run the named suites with the hook bound and migrate only the listed assertions the forced retro changes, as the ticket requires. If a suite really shows no change, state in the run record why the forced retro does not fire there.)
