---
verdict: snag
reviewed_sha: 9dde3ee4c4437df9425cca4bb45fa7d3d5de6499
produced_by_spec_version: '1.0'
produced_at_sha: 9dde3ee4c4437df9425cca4bb45fa7d3d5de6499
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The emitted tickets and most of the pins match the ticket. The on-demand fault-reference exceptions are only weakly pinned: the test checks that they are absent from Context, but not that the runner seed declares them as on-demand references.

## Findings
- correctness_review at tests/test_seeded_phase3_21.py:109: Acceptance criterion 2 requires the test to pin 'the two on-demand fault-reference exceptions'. The only assertion that touches ON_DEMAND is `set(ON_DEMAND['daemon-soak-runner']).isdisjoint(runner.context)`. That assertion passes even if the daemon-soak-runner ticket stops mentioning `tests/test_restart_timers.py` and `tests/test_mergequeue.py`, or if either one is swapped for another path. It checks only that they are absent, not that the exception exists. Unlike the precedent seeded tests, these paths are not in the runner's fence, so no `ON_DEMAND <= scope_fence` check covers them either. I am fairly confident this is a gap in meeting the criterion, not a style point. (paved road: Pin the exceptions positively. For each path in ON_DEMAND['daemon-soak-runner'], assert that it appears in `_section('daemon-soak-runner', 'Scope in')` in its on-demand sentence, for example `tests/test_restart_timers.py` is the on-demand worker-reconcile fault reference and `tests/test_mergequeue.py` is the on-demand two-rung and integration-red fault reference. Keep the existing disjointness check against Context and the fence.)
