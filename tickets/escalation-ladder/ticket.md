---
state: confirmed
source: seed
priority: P1
kind: feature
# section 19 pre-ladder tier rule: every code-bearing Phase 2 seed runs at the
# HIGH tier until the escalation ladder merges; effort stays at the default.
agent_tier: high
agent_effort: medium
---
## Depends on
- reject-queue

## Context
- squatch/runner.py
- squatch/stages.py
- squatch/drain.py
- squatch/providers.py
- squatch/llm.py
- squatch/config.py
- squatch/tickets.py
- config.yaml
- tests/test_terminal.py
- tests/test_drain.py

## Plan contract
- section 11
- section 9

## Goal
The capability ladder routes a repeat offender onward deterministically: an `escalate` verdict, a retry that returns to the same gate wall, K identical terminal reasons, and an oscillating snag list climb one rung -- tier first to the next DIFFERENT model, then effort toward `max` -- with the rung recorded on the re-offer's `cap_consumed` draw and folded per lineage, the effective (tier, effort) resolved at dispatch with `ticket.md` never edited, and RMA to the Reject queue only when the ladder is exhausted.

## Why
Section 11.4: the model RECOMMENDS escalation and never picks its own tier; the deterministic layer walks the ladder model-first because the model is the dominant capability lever and nothing sits above the top one, skipping a bump that resolves the same model so no attempt is wasted on a no-op. The rung is journal-derived -- it rides the retry draw the re-offer already journals -- so escalation never edits the ticket, an edit never changes a rung, and the operator's keep is the one event that resets both. Returning to an identical wall is never findings-fed progress: a retry still failing the gate code it was dispatched to clear, K consecutive identical terminal reasons, or alternating snag lists climb instead of re-running at the same rung, and short-circuit to Reject only when the ladder is exhausted. Section 11.1 sizes the caps so a stem can climb every rung and still land at the top; this ticket is why the pre-ladder tier rule of section 19 ends: seeds authored after it merges may start at `medium` with somewhere to climb. It depends on `reject-queue` because every arm's fall-through is that queue, and a Reject arrival needs its verbs and projection live.

## Scope in
A new module `squatch/ladder.py` owning the rung walk and its fold. `Rung(tier, effort)` over the closed `low < medium < high < max` scales. `next_rung(registry, current) -> Rung | None`: the next tier above `current.tier` whose `implement` routing (`Registry.resolve(tier, "implement")`) yields a (provider, model) DIFFERENT from the current rung's, skipping every same-model tier; when no higher tier resolves a different model, `current.effort` one step toward `max`; `None` at the top model and `max` effort (the ladder is exhausted). `rungs(events, stem) -> Rung | None`: the latest `rung` body on the lineage's retry-named `cap_consumed` draws, bounded like the caps by the stem's latest operator `confirm` signal (a keep resets rungs and caps together), a machine `confirm` never bounding it. `effective(ticket, rung) -> (tier, effort)`: the authored frontmatter when no rung is folded, else the rung. `IDENTICAL_TERMINALS` = 3 is the engine constant K. `identical(events, stem) -> bool`: the stem's last K terminals since its latest operator keep carry the same outcome and the same terminal reason (the section 11.4 comparison key -- the code-only reason, never the harvested detail); `same_wall(events, stem, delivery) -> bool`: the latest attempt was a re-offer dispatched after a `gate_failed` terminal and ended `gate_failed` on the same gate code; `oscillating(events, stem) -> bool`: the last three terminals' finding-code lists alternate A, B, A. `squatch/reject.py`'s `route` gains the ladder arms between its null-verdict arm and its verdict arms, in this fixed order, each resolving to `routed: ladder` with `rung` = `next_rung(...)` when a rung exists and to the Reject marker with a reason naming the exhausted ladder when it does not: (a) `oscillating`; (b) `identical`; (c) verdict `escalate`; (d) verdict `retry` with `same_wall`; verdict `retry` otherwise re-runs at the current rung with no marker. `squatch/runner.py`: the terminal body carries `routed: ladder` and `rung` when the routing set them (the `routed` value set becomes exactly `reject_queue | ladder`), and `Runner.dispatch` resolves the effective (tier, effort) through `rungs` and `effective` on EVERY dispatch -- `run <stem>` and the drain share the path -- handing the stages a ticket whose `agent_tier`/`agent_effort` are the effective ones (`dataclasses.replace`; the committed `ticket.md` is never written) so the `LLMRequest` of every implement, review, and diagnose call records the rung. `squatch/drain.py`: a re-offer of a stem whose latest terminal carries `routed: ladder` records that `rung` on the body of the retry `cap_consumed` it already journals, and its re-offer line names the rung; nothing else in eligibility, park, or re-offer changes. `squatch/stages.py` is fenced per the section 19 ownership law; it changes only if the effective capability cannot reach the driver through the ticket it is handed. Tests for every rule above; read `squatch/reject.py`, `squatch/caps.py`, and `tests/test_reject.py` in the worktree (they land with the `depends`); the same-model skip is pinned under a routing fixture shaped like this checkout's `config.yaml` (`high` and `max` sharing one model).

## Scope out
No Rework, no `split` dispatch (a `split` verdict stays Reject-routed), no supersedes map, no watchdog spiral signal (Phase 4; the cross-attempt analog is this ticket's identical-terminal rule). No review-surface escalation: review stays pinned to its routed tier (section 20), only the implement surface's rung walks. No drought exemption from the identical-terminal rule: no drought producer exists yet, so it lands with the breaker. No change to the verbs, to the cap fold's bound beyond reading it for rungs, to the auto-keep, to `ticket.md`, to `specs/`, to `config.yaml`, or to any frontmatter field, config key, cap, or event type.

## Scope fence
- squatch/ladder.py
- squatch/reject.py
- squatch/runner.py
- squatch/stages.py
- squatch/drain.py
- tests/test_ladder.py
- tests/test_reject.py
- tests/test_terminal.py
- tests/test_drain.py

## Acceptance criteria
- In `tests/test_ladder.py`, under a routing fixture where `implement` resolves distinct models at `low`, `medium`, `high` and the same model at `max`, `next_rung` walks `(medium, medium)` to `(high, medium)`, then to `(high, high)` (the `max` tier skipped as a same-model no-op), then to `(high, max)`, then `None`; `IDENTICAL_TERMINALS` equals 3.
- In `tests/test_ladder.py`, `rungs` folds the latest `rung` from a lineage's retry draws, ignores a draw naming another cap, and returns `None` once an operator `confirm` signal follows the draws while a machine `confirm` leaves it folded; `identical` is true for three consecutive `gate_failed` terminals with one reason and false when the third differs or an operator keep sits between them; `oscillating` is true for finding-code lists A, B, A and false for A, A, B.
- In `tests/test_reject.py`, `route` returns `routed: ladder` with the next rung for an `escalate` verdict with rungs remaining and the Reject marker naming the exhausted ladder at the top rung; a `retry` verdict returning to the same gate code climbs, and a `retry` clearing it re-runs with no marker; the spent-cap arm still precedes every ladder arm.
- In `tests/test_terminal.py`, a run whose diagnosis verdict is `escalate` journals its terminal with `routed: ladder` and a `rung` body, and no arrival signal; a run at the top rung with `escalate` journals `routed: reject_queue` and the arrival.
- In `tests/test_drain.py`, after an `escalate` terminal the stem's re-offer journals its retry `cap_consumed` with the `rung` body, the fake pipeline receives a ticket whose `agent_tier`/`agent_effort` equal that rung while `tickets/<stem>/ticket.md` on main is byte-identical to its authored content, and the re-offer line names the rung; a stem ending `gate_failed` with one gate code three times climbs on the third terminal instead of a fourth same-rung re-offer; a stem that exhausts the ladder is reported under `reject queue:`.
- In `tests/test_drain.py`, `squatch confirm <stem>` (operator) after two rungs makes the next dispatch run at the authored frontmatter capability.
- `grep -rn "IDENTICAL_TERMINALS = " squatch` reports exactly one definition, in `squatch/ladder.py`.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_ladder.py tests/test_reject.py -q
uv run pytest tests/test_terminal.py tests/test_drain.py -q
grep -rn "IDENTICAL_TERMINALS = " squatch
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` if the effective capability cannot reach the stage layer through the `Ticket` the runner hands it without editing `ticket.md` or changing `specs/`, if the rung cannot ride the retry draw's `cap_consumed` body as the caps writer landed it, if `Registry.resolve` as landed cannot answer the implement surface per tier, if any file outside the fence must change, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 90m
- stuck: 180m
