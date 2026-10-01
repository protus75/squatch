---
kind: bug
priority: P3
agent_tier: medium
agent_effort: medium
source: box:suggestion
state: draft
---

## Depends on
- none

## Context
- squatch/providers.py
- tests/test_providers.py

## Plan contract
- section 6

## Goal
`LLMResult.input_tokens` means the same thing for every `cli` adapter: the total prompt tokens a call processed, cached and uncached together. `ClaudeAdapter.parse` folds the `result` event usage's `cache_creation_input_tokens` and `cache_read_input_tokens` into `input_tokens` (a missing cache field counts as zero; `input_tokens` stays `None` when the stream reports no usage at all), matching what `CodexAdapter.parse` already reports from `turn.completed`. Section 6's `LLMResult.input_tokens` comment in `SQUATCH_PLAN.md` states this one meaning explicitly.

## Why
`squatch/retro.py`'s retro window and `squatch/driver.py`'s `Cost.fold` both sum `input_tokens` from every `effect_completion` without checking which provider produced it. Today the claude adapter reports only the uncached slice of a prompt, so on a cached multi-KB prompt that figure can read in the single digits, while the codex adapter reports its CLI loop's cumulative prompt total. Any cross-provider token total, and any spend projection built on one, mixes two different measurements and badly undercounts claude's share. The plan never defines the field today, so the fix lands in the plan first and is then carried into the adapter -- one normalized meaning, no per-adapter interpretation flag, keeps every consumer on a single path.

## Scope in
- `squatch/providers.py`: `ClaudeAdapter.parse`'s `input_tokens` computation.
- `SQUATCH_PLAN.md`: section 6's `LLMResult.input_tokens` comment.
- `tests/test_providers.py`: a claude case with nonzero cache-read and cache-creation usage, and a codex case pinning that its cached input is not added a second time.

## Scope out
- `CodexAdapter.parse` (already reports the cumulative, cache-inclusive total; unchanged).
- The `effect_completion` cost body shape, `Cost.fold` in `squatch/driver.py`, and the retro window's `tokens` fold in `squatch/retro.py` -- they keep summing `input_tokens` as-is; only the figures they sum change meaning.

## Scope fence
- squatch/providers.py
- SQUATCH_PLAN.md
- tests/test_providers.py

## Acceptance criteria
- `SQUATCH_PLAN.md` section 6 states that `LLMResult.input_tokens` is the total prompt tokens a call processed, cached and uncached together, for every `cli` adapter (checked by `grep -n input_tokens SQUATCH_PLAN.md`).
- `ClaudeAdapter.parse` returns `input_tokens` equal to the `result` event usage's `input_tokens` plus `cache_creation_input_tokens` plus `cache_read_input_tokens`, treating an absent cache field as zero, and returns `None` when the stream reports no usage at all (checked by `pytest tests/test_providers.py -q`).
- `CodexAdapter.parse`'s `input_tokens` computation is unchanged (checked by `pytest tests/test_providers.py -q`).
- The full provider test file passes (checked by `pytest tests/test_providers.py -q`).

## Verification
```
pytest tests/test_providers.py -q
grep -n input_tokens SQUATCH_PLAN.md
```

## Regression
```
pytest tests/test_providers.py::test_claude_adapter_parse_folds_cache_tokens_into_input_tokens -q
```
- carries: tests/test_providers.py

## Definition of rejected
Stop and throw the branch away if folding the cache fields into `input_tokens` turns out to require changing the `effect_completion` cost body shape, `Cost.fold`, or the retro `tokens` fold -- that is a wider change than this ticket's scope and belongs in a follow-up, not something absorbed here.

## Time budget
- expected: 30m
- stuck: 90m
