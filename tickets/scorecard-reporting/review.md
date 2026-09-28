---
verdict: snag
reviewed_sha: 78ea56c02f5f5abf33c36dfd570edad8c7571b34
produced_by_spec_version: '1.0'
produced_at_sha: 78ea56c02f5f5abf33c36dfd570edad8c7571b34
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The implementation is correct and matches the real check-invoice key and shape (`effect_key("check", stem, run_seq)` with `invoice.checks[{code, verdict, bypassed}]`). It stays inside the fence and leaves tests/test_retro.py unchanged. Two acceptance criteria are only partly proven: the tests never exercise the below-threshold side of the 25-ticket prune rule, and they never show that the projection makes no writes or effects.

## Findings
- correctness_review at tests/test_scorecard.py:70: The acceptance criteria require the tests to prove the 25-ticket prune threshold, but only the 25-ticket case (prune_candidate True) is tested. No case has 24 distinct zero-catch tickets expecting False. If the implementation were changed to `evaluated_tickets >= 2` (or any value from 2 to 25), every test would still pass. The only below-threshold zero-catch row is the 1-ticket `zeta` row in the render test, which catches nothing above `>= 1`. (paved road: Add a boundary case: 24 distinct tickets with only passing observations for one code must give prune_candidate False, next to the existing 25-ticket True case. Optionally add a 25-ticket code with one catch to show that a catch blocks pruning.)
- correctness_review at tests/test_scorecard.py:77: The acceptance criteria require proof that the projection 'leaves its input unchanged while performing no writes or effects'. The test only compares `projection.model_dump()` before and after, which covers immutability. Nothing covers writes or effects: no filesystem, journal, Git, Box, or provider seam is monitored or made to fail. This is uncertain, because `project_scorecard` takes no seam argument and so has no injected seam to call, but the criterion asks for proof and the test makes none. (paved road: Make the no-effect guarantee testable. For example, run `project_scorecard` inside a test that monkeypatches `builtins.open`, `pathlib.Path.write_text`/`write_bytes`, and `subprocess` entry points to raise, and check that the scorecard still returns. Alternatively, assert that `squatch.scorecard`'s module imports are limited to `collections`, `typing`, and `squatch.artifacts`.)
