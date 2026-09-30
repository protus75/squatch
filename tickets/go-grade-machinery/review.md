---
verdict: snag
reviewed_sha: 48814d4961962972caf5d49e8cd14b676c0bfff4
produced_by_spec_version: '1.0'
produced_at_sha: 48814d4961962972caf5d49e8cd14b676c0bfff4
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
Registration, the closed report and the operator GO path look sound. But run_go_grade hardcodes run_seq=0, so its calls use the same journal/spool keys as ordinary baseline runs and earlier go-grade runs. Its spend cap is also only checked after a call has already pushed spend past USD 5.00.

## Findings
- correctness_review at eval/harness.py:460: run_go_grade passes run_seq=0 to every driver.run call: the Author at attempt 0 and the 50 reviews at attempts 1..50. The ordinary `run` sets run_seq to the count of prior review_baseline signals. That count exists so a rerun after a recorded verdict gets fresh keys, while a rerun after an unscored run replays attempts it already completed. With run_seq fixed at 0, a go-grade run after any recorded baseline shares keys with the first ordinary run. Attempts 1..N then replay results from different fixtures (or from an earlier go-grade run) instead of calling the model. The scores and spend become fabricated evidence, and every go-grade run after the first gets no fresh keys. The go-grade test uses a fresh tmp_path journal, so it does not catch this. (paved road: Compute run_seq the same way `run` does (count of prior SIGNAL_KIND signals in the journal), or share one helper between both paths. Add a test that runs the ordinary `run` first, then run_go_grade, and asserts that the go-grade run makes all 51 model calls and does not replay the earlier results.)
- correctness_review at eval/harness.py:428: _within_cap only runs before a call, and only compares spend already charged. One call can therefore take the real spend past the fixed USD 5.00 cap. Example: Author 4.99 plus one review at 0.02 gives 5.01. The test test_running_cap_counts_author_and_refuses_before_another_review expects exactly that overflowing review call. The ticket's Definition of rejected lists 'overflow'. A 'fixed cap' that allows up to one call's cost above USD 5.00 does not bound spend. The error message 'no further model call was made' is misleading, because the call that crossed the cap was made. I am not certain the ticket means a strict pre-call reservation, so the stated intent should be checked. (paved road: Before each call, refuse unless the remaining headroom covers a conservative per-call bound, e.g. the largest cost seen so far or a configured per-call ceiling, so charged spend cannot exceed GO_SPEND_CAP_USD. Update the test so the refused call is never issued and the recorded spend stays <= 5.00. Alternatively, document exactly how much overshoot the cap allows and make the error message match.)
