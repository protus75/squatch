---
verdict: snag
reviewed_sha: 758a3c3b3b9f25eb1384c926f357a86c4a711e41
produced_by_spec_version: '1.0'
produced_at_sha: 758a3c3b3b9f25eb1384c926f357a86c4a711e41
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The diff meets every acceptance criterion and stays inside the fence. One defect remains: the partial-lift recovery in `_prior_lifted` resets its accumulated seeds whenever a new lift intent appears. After two interrupted lifts, the seeder's own lifted seed is treated as a foreign collision and the stem can never be re-run.

## Findings
- correctness_review at squatch/seeds.py:151: `_prior_lifted` sets `partial = set()` on every `lift/<seeder>/*/seeds` intent. `Effects.run` journals no completion when the action raises, so a crashed lift stays open. Failing scenario: (1) run 0's lift commits alpha-seed (a `ticket_intake` signal), then fails on beta-seed. (2) run 1's lift finds alpha already on HEAD with the reviewed sha. It takes the replay branch in `_lift_seeds`, which journals no new `ticket_intake`, and then fails again on beta. (3) At run 2, `_prior_lifted` sees the run-1 intent, resets `partial` to empty, and finds no `seed_lift` signal. `validate_batch` then reports alpha-seed as `already exists on main`. The collision is permanent, so every later re-offer is refused. That breaks section 19's RE-RUN rule and leaves a hold with no reachable release. (paved road: Collect partial intakes across every open (uncompleted) `lift/<seeder>/*/seeds` intent instead of resetting on each new intent. One way is to take the union of `source: seed` intake stems seen since the seeder's last completed lift. Another is to have the replay path in `_lift_seeds` journal something the fold can see. Add a `tests/test_terminal.py` case that interrupts the lift twice, then shows a third run lifts without a collision finding.)
