---
verdict: snag
reviewed_sha: ec94bbb5359cd809c29af31cf7f83159ec21a233
produced_by_spec_version: '1.0'
produced_at_sha: ec94bbb5359cd809c29af31cf7f83159ec21a233
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The routing, the fold, the runner's terminal marker, the drain's auto-keep and legacy arrival, and status all match the ticket, and the checks are green. One gap: the new drain test for the auto-kept marked stem does not show that the stem was kept out of the eligible set or that it merged after the green re-run, and the ticket's acceptance criterion requires both.

## Findings
- correctness_review at tests/test_drain.py:228: The acceptance criterion says a marked stem with `retry` budget left is not in the eligible set, is re-offered in the same drain after a machine `confirm` and one `retry` draw, and merges when its re-run is green. `test_marked_arrival_auto_keeps_then_reoffers_with_one_retry_draw` checks the machine confirm, the single `retry` draw, the call, and the `re-offer: base` line. It never checks that the stem merged, and it never checks that the machine `confirm` comes before the re-run. So the 'merges' and 'confirm first' parts of the criterion are not checked. (paved road: Add `assert states(checkout, "base")[-1] == "merged"` to that test. Also assert that the machine `confirm` signal's journal index is lower than the index of base's second `running` transition, so the test proves the hold was released by the auto-keep and not by ordinary eligibility.)
