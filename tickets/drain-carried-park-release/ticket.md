---
priority: P3
kind: bug
agent_tier: medium
agent_effort: medium
source: box:suggestion
state: draft
---
## Depends on
- none

## Context
- squatch/drain.py
- tests/test_drain_upgrade.py
- tests/test_drain.py

## Plan contract
- section 18

## Goal
In `squatch/drain.py`, `Drain._parked` drops a carried stem (one passed in via a self-upgrade handoff's `--parked` flags, held in `self._carried`) from the returned parked set once `self._released(facts, stem)` reports it released -- the same `_released` check `_eligible` already uses, for every reason it recognizes: a premise-parked ticket's `ticket.md` edit with bounce-cap budget remaining, an operator confirm, or a `provider_cooldown` terminal. A carried stem `_released` does not yet clear stays parked exactly as today. The `squatch/drain.py` module docstring's handoff paragraph is corrected to match: a carried park holds across the handoff only while the child's own `_released` fold keeps reporting it parked, not unconditionally. `tests/test_drain_upgrade.py` gains a regression test proving the fixed case on a real self-upgrade handoff: a child drain carries a premise-parked stem via `--parked`, that stem's `ticket.md` is edited with bounce-cap budget remaining (the release, intaken at the child's entry), and the child is driven to the `drain.max_runtime_hours` ceiling halt before that stem's turn to dispatch -- so it is released but still undispatched when the report prints. The test asserts the stem is dispatched zero times and that no `parked: <stem>` line appears in the halted report.

## Why
`_eligible` (drain.py:348-355) already checks `_released` before treating a ticket as dispatchable, but `_parked` (drain.py:364-367) unions `self._carried` into the parked set with no release check at all. So once a carried stem clears `_released`, it is eligible for dispatch, yet `_parked` -- and therefore `_tail`'s `parked:` line, `_resolve_rejects`, and the next `_handoff`'s re-carry -- still treats it as parked for as long as it has not yet been dispatched when one of those runs. That happens whenever a report prints before the released stem reaches its turn: a `drain.max_runtime_hours` ceiling halt, or a released stem still blocked behind an earlier, unmerged `depends`. The existing self-upgrade coverage (`test_retry_budget_spent_before_the_re_exec_stays_spent_in_the_child`) only exercises a carried stem `_released` keeps refusing (its cap is spent), so it proves nothing about the released case. A report that treats a stem as released for dispatch purposes but still names it `parked:` breaks the report's role as the operator's paved road to the actual state. The module docstring's claim that the parent's verdicts hold unconditionally across the handoff is also wrong once this lands, since the child's own journal fold can now override a carried park.

## Scope in
In `Drain._parked`, filter `self._carried & plane.tickets.keys()` through `self._released(facts, s)` before unioning it with the existing non-carried parked set, dropping any carried stem `_released` reports true for. Reuse `self._released` as-is; do not add a second, narrower release check. Amend the `squatch/drain.py` module docstring's handoff paragraph -- the sentence ending "and the parent's verdicts hold" -- to say a carried park holds only while the child's own `_released` fold keeps reporting it parked, and that a release journaled after the handoff (a ticket-plane edit, an operator confirm, or a provider cooldown) drops a carried stem from the parked set instead of re-parking it.

Add one test to `tests/test_drain_upgrade.py`: commit a premise-bound ticket (`caps.premise_bounce` configured to 2) and run a parent drain that dispatches it once to a `premise_failed` terminal, drawing 1 of 2 premise_bounce units, then self-upgrades (`touches` a `squatch/**` path on another ticket) so the handoff carries it via `--parked`. Before the child runs, edit the parked stem's `ticket.md` (uncommitted, so the child's own entry intake commits and journals it -- the same mechanism `test_a_premise_failed_stem_draws_and_runs_again_after_edit_then_confirm` relies on) so `_released` clears it (edited, remaining budget 1 > 0). Commit one more ticket with an earlier `signal_at` so it sorts first in the child. Run the child drain (give the local `drain()` helper in `tests/test_drain_upgrade.py` an optional `clock` parameter, defaulting to a fresh `FakeClock()`, mirroring the one in `tests/test_drain.py`) with a `FakeClock` an `on_run` hook advances past `drain.max_runtime_hours` while dispatching the earlier-sorted ticket, so the released, carried, premise stem is still undispatched when the ceiling halts the next dispatch and `_tail` prints. Assert the released stem is dispatched zero times in the child invocation, the halt report names it as next, and no `parked: <stem>` line appears anywhere in the output. Confirm the test fails on the base commit (today's unconditional carried union) before the fix lands, for the reason named here -- not for an unrelated setup defect.

## Scope out
No change to `_eligible`, to any of `_released`'s own release conditions, to `_resolve_rejects`'s reject-queue logic, to `_reoffers`, to the premise-bounce cap mechanics, to any other `_tail` report line, or to section 18's argv-carry rule (the handoff still carries the invocation's parked set as repeated `--parked` flags). No file outside the two fenced paths changes.

## Scope fence
- squatch/drain.py
- tests/test_drain_upgrade.py

## Acceptance criteria
- `Drain._parked` excludes a carried stem from its returned list whenever `self._released(facts, stem)` is true, for every `_released` reason (premise edit with remaining bounce-cap budget, operator confirm, provider cooldown), checked by `uv run pytest tests/test_drain_upgrade.py -q`.
- The `squatch/drain.py` module docstring no longer states the parent's verdicts hold unconditionally across the handoff; it states a carried park holds only while `_released` keeps reporting it parked.
- The new regression test fails on the base commit and passes after the fix: a released carried stem still undispatched when the ceiling-halt report prints is dispatched zero times and never gets a `parked: <stem>` line, checked by `uv run pytest tests/test_drain_upgrade.py -k test_a_released_carried_stem_still_undispatched_at_halt_is_not_reported_parked -q`.
- `uv run pytest tests/test_drain_upgrade.py tests/test_drain.py -q` exits 0.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_drain_upgrade.py -k test_a_released_carried_stem_still_undispatched_at_halt_is_not_reported_parked -q
uv run pytest tests/test_drain_upgrade.py tests/test_drain.py -q
uv run pytest -q
```

## Regression
```
uv run pytest tests/test_drain_upgrade.py -k test_a_released_carried_stem_still_undispatched_at_halt_is_not_reported_parked -q
```
- carries: tests/test_drain_upgrade.py

## Definition of rejected
Stop and answer premise_failed if the fix cannot be expressed as a release filter inside `_parked` alone (for example if `_resolve_rejects` or `_eligible` must also change), or if the new test cannot be made to fail on the base commit for the reported reason (a released-but-undispatched carried stem still printed `parked:`).

## Time budget
- expected: 30m
- stuck: 60m
