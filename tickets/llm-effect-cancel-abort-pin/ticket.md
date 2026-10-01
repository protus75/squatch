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
- squatch/llmeffect.py
- tests/test_llm_effect.py
- tests/test_driver.py

## Goal
`tests/test_llm_effect.py` gains a test that calls an `LLMEffect` directly against a `FakeLLM` configured to hang and ignore cancellation, cancels the outer task while the call is in flight, and asserts: `asyncio.CancelledError` propagates out of the call, the fake LLM's `aborted` count is `1`, and the journal holds exactly one `effect_intent` event and no `effect_completion` event. `squatch/llmeffect.py` and `tests/test_driver.py` are unchanged.

## Why
`LLMEffect._call` has two kill paths. The stuck-budget path (`Stuck`) is already pinned at the effect surface by `test_effect_stuck_call_is_aborted_and_leaves_intent_only`. The outer-cancellation path -- the `except asyncio.CancelledError` branch that calls `_abort` and re-raises -- is today exercised only indirectly, through the Driver's cancellation test in `tests/test_driver.py`. A direct effect-surface test keeps that crash point pinned next to the code that owns it, so a future change to the Driver's cancellation wiring can no longer silently stop exercising it.

## Scope in
- One new test in `tests/test_llm_effect.py` that cancels an in-flight `LLMEffect` call (following the existing `llm_effect`/`call`/`journal` helpers and the `Hang`-based fixture pattern already used by the stuck-budget tests in the same file) and asserts the three outcomes above.

## Scope out
- Any change to `squatch/llmeffect.py` -- the kill path already exists and is only being pinned, not altered.
- The existing Driver-level cancellation test in `tests/test_driver.py` -- left exactly as it is.
- The stuck-budget (`Stuck`) kill path -- already covered by existing tests in this file.

## Scope fence
- tests/test_llm_effect.py

## Acceptance criteria
- `tests/test_llm_effect.py` contains a test that cancels an in-flight `LLMEffect` call against a hanging `FakeLLM` and asserts `asyncio.CancelledError` propagates out of the call: checked by `pytest tests/test_llm_effect.py -k outer_cancel -q`.
- The same test asserts the fake LLM's `aborted` count equals 1 after the cancellation: checked by `pytest tests/test_llm_effect.py -k outer_cancel -q`.
- The same test asserts the journal contains exactly one `effect_intent` event and no `effect_completion` event after the cancelled call: checked by `pytest tests/test_llm_effect.py -k outer_cancel -q`.
- The full existing suites in `tests/test_llm_effect.py` and `tests/test_driver.py` still pass unchanged: checked by `pytest tests/test_llm_effect.py tests/test_driver.py -q`.

## Verification
```
pytest tests/test_llm_effect.py -k outer_cancel -q
pytest tests/test_llm_effect.py tests/test_driver.py -q
```

## Definition of rejected
Stop and throw the branch away if pinning the outer-cancellation path at the effect surface turns out to require changing `squatch/llmeffect.py` or the Driver's cancellation wiring -- that is a different, larger change than adding a test, and belongs in its own ticket.

## Time budget
- expected: 20m
- stuck: 45m
