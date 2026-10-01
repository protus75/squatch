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
- squatch/reconcile.py
- tests/test_reconcile.py

## Goal
`reconcile`'s operator-facing report line for a reaped orphan names the evidence that made it an orphan. An orphan with a dangling `running` (no terminal after it) keeps today's "was left `running`" wording. An orphan that is only an open `effect_intent` after the stem's last terminal, with no dangling `running`, is reported naming its open intent key(s) and never claims the run was left `running`. `Orphan` carries an explicit field recording which case applies, since a non-empty `open_keys` alone cannot distinguish them (a `running` orphan can also have open intents).

## Why
`orphans` (`squatch/reconcile.py:44`) folds the journal into two distinct orphan causes: a dangling `running`, or an open intent surviving past the last terminal. `reconcile`'s report at `squatch/reconcile.py:116` is one fixed string that always says "was left `running`", so the intent-only case tells the operator a `running` exists when the journal has none, pointing them at the wrong evidence when they inspect the reaped run. The engine-log `reconcile` event already carries `open_keys` (`squatch/reconcile.py:114`); only the operator line is wrong.

## Scope in
- `squatch/reconcile.py`: `Orphan` gains a field recording whether the orphan has a dangling `running` (vs. intent-only), and `orphans()` sets it correctly for every returned `Orphan`.
- `squatch/reconcile.py`: the `report(...)` call in `reconcile()` is worded from that field -- "was left `running`" only when it is a dangling-`running` orphan; an intent-only orphan names its open key(s) and omits "left `running`".
- `tests/test_reconcile.py`: `test_orphans_is_a_running_with_no_terminal_or_an_intent_with_no_completion`'s expected `Orphan` values are updated to state the new field explicitly -- the dangling-`running` value for `twice`, the intent-only value for `intent`.
- `tests/test_reconcile.py`: a new test journals an intent-only orphan (a `running` with a terminal after it, then an `effect_intent` with no completion and no further `running`) and asserts, over the `run` CLI's output, that the report line names the open key and does not contain "left `running`".

## Scope out
- The engine-log `reconcile` event's `open_keys` field (`squatch/reconcile.py:114`) -- already correct, unchanged.
- The `stems` set computation in `orphans()` that decides which stems count as orphans at all -- unchanged; only the new descriptive field on `Orphan`.
- Any orphan cause beyond the two `orphans()` already distinguishes.

## Scope fence
- squatch/reconcile.py
- tests/test_reconcile.py

## Acceptance criteria
- `Orphan` carries a field stating whether the orphan has a dangling `running`, true for a dangling-`running` orphan and false for an intent-only orphan, including when a `running` orphan also has open intents (checked by `pytest tests/test_reconcile.py -k test_orphans_is_a_running_with_no_terminal_or_an_intent_with_no_completion -q`).
- A reaped orphan with a dangling `running` still reports "was left `running`" (checked by `pytest tests/test_reconcile.py -k test_an_orphaned_running_is_reaped_abandoned_and_its_worktree_removed_on_the_next_run -q`).
- A reaped intent-only orphan reports its open intent key(s) and the report line does not contain "left `running`" (checked by the new test, `pytest tests/test_reconcile.py -k test_an_orphan_by_intent_alone_is_reported_without_claiming_running -q`).
- The full reconcile test file passes (checked by `pytest tests/test_reconcile.py -q`).

## Verification
```
pytest tests/test_reconcile.py -q
pytest tests/test_reconcile.py -k test_orphans_is_a_running_with_no_terminal_or_an_intent_with_no_completion -q
```

## Regression
```
pytest tests/test_reconcile.py -k test_an_orphan_by_intent_alone_is_reported_without_claiming_running -q
```
- carries: tests/test_reconcile.py

## Definition of rejected
Stop and throw the branch away if distinguishing the two causes turns out to need a change to which stems `orphans()` counts as orphaned, or to the `effect_intent`/`effect_completion` fold itself -- that is a wider change than this ticket's scope and belongs in a follow-up, not something absorbed here.

## Time budget
- expected: 25m
- stuck: 60m
