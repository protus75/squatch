---
kind: chore
priority: P3
agent_tier: medium
agent_effort: medium
source: box:suggestion
state: draft
---

## Depends on
- none

## Context
- eval/harness.py
- squatch/stages.py

## Goal
`eval/harness.py` stops defining its own `ReviewReport` class and its own `ReviewVerdict` literal, and instead imports both from `squatch/stages.py` (`ReviewReport` and `ReviewVerdictName`). The local `ReviewVerdict = Literal["approve", "snag", "rma"]` and the local `class ReviewReport(Artifact)` (fields `verdict`/`summary`/`findings`, with the validator requiring empty `findings` exactly when `verdict` is `approve`) are deleted; every existing reference in the harness (`Expected.expected_verdict`, `Score.expected_verdict`, `Score.verdict`, and every place that parses or scores a `ReviewReport`) now resolves to the engine's type instead of a byte-for-byte local copy. `ReviewInput` stays defined in `eval/harness.py`, since `squatch/stages.py`'s wired review stage consumes its own `Invoice` input, not an importable equivalent. The eval and engine test suites pass unchanged, and the registered review-baseline report schema is untouched.

## Why
`squatch/stages.py:224-235` and `eval/harness.py:228-242` carry the same review-output contract (`verdict`/`summary`/`findings`, same empty-findings-iff-approve rule) as two separately maintained classes. If `specs/review.md`'s output format ever changes, the engine's copy can be updated while the harness's copy is forgotten, and the GO-grade/baseline harness would then silently grade review output against a contract the wired Review stage no longer admits -- the exact dual-path drift the no-dual-path rule exists to prevent. The harness already imports several `squatch.*` engine modules (`squatch.driver`, `squatch.config`, `squatch.providers`, among others), so importing `squatch.stages` adds no new kind of dependency, only removes a duplicate one.

## Scope in
- In `eval/harness.py`, delete the local `ReviewVerdict = Literal["approve", "snag", "rma"]` definition and the local `class ReviewReport(Artifact)` definition (including its `_findings_match_verdict` validator).
- Import `ReviewReport` and `ReviewVerdictName` from `squatch.stages` in their place, for example `from squatch.stages import ReviewReport, ReviewVerdictName as ReviewVerdict`, so every existing local reference to the name `ReviewVerdict` (`Expected.expected_verdict`, `Score.expected_verdict`, `Score.verdict`) keeps resolving without a rename, and every existing local reference to `ReviewReport` (construction, `isinstance` checks, scoring) keeps working against the imported class.
- Leave `ReviewInput`, `review_stage`, `score`, `summarize`, and every other harness function and class exactly as they behave today; only the two duplicated type definitions move to an import.

## Scope out
- `squatch/stages.py` is not edited; this ticket removes the harness's duplicate, not the engine's original.
- `ReviewInput` is not touched, renamed, or moved; the engine has no matching class to import for it.
- The registered review-baseline report schema (`REVIEW_BASELINE_REPORT`, `ReviewBaselineReport`, `ReviewBaselineSummary` in `squatch/artifacts.py`) is unchanged.
- No change to `specs/review.md`, the Review stage's gates, or `emits_by_verdict` wiring.

## Scope fence
- eval/harness.py

## Acceptance criteria
- `eval/harness.py` contains no local `class ReviewReport` definition and no local `ReviewVerdict = Literal[...]` definition; checked by `grep -n "class ReviewReport\|^ReviewVerdict = Literal" eval/harness.py` printing nothing.
- `eval/harness.py` imports `ReviewReport` and `ReviewVerdictName` from `squatch.stages`; checked by `grep -n "from squatch.stages import" eval/harness.py` printing a line naming both.
- `pytest tests/test_eval_harness.py tests/test_go_grade.py tests/test_stages.py -q` exits 0.
- `pytest -q` exits 0.

## Verification
```
grep -n "class ReviewReport\|^ReviewVerdict = Literal" eval/harness.py
grep -n "from squatch.stages import" eval/harness.py
pytest tests/test_eval_harness.py tests/test_go_grade.py tests/test_stages.py -q
pytest -q
```

## Definition of rejected
Stop and throw the branch away if removing the duplicate turns out to require changing `squatch/stages.py`'s `ReviewReport` fields, its validator, or the registered review-baseline report schema to make the import fit -- that is a larger contract change than this ticket covers, and the mismatch itself is a second problem to file, not to fix inline here.

## Time budget
- expected: 30m
- stuck: 60m
