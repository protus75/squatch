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
- reject-verbs
- diagnosis-eval-run

## Context
- squatch/runner.py
- squatch/stages.py
- squatch/drain.py
- squatch/status.py
- tests/test_terminal.py
- tests/test_drain.py
- tests/test_drain_upgrade.py
- tests/test_cli.py

## Plan contract
- section 11
- section 9
- section 13

## Goal
The Reject queue is live as a journal-derived projection: the terminal handler's deterministic routing stamps `routed: reject_queue` on the run's single terminal for a spent spine cap, a null diagnosis verdict, and the `reject`, `abandon-human`, and `split` verdicts, journals the Reject-queue arrival escalation, the drain excludes an awaiting stem from eligibility, auto-keeps it with a machine-actor `confirm` while no spine cap is spent, and otherwise holds it for the operator's `confirm`/`reject`; `status` lists the queue.

## Why
Section 11.4: the sandwich's last layer is deterministic dispatch on the verdict string, and RMA to the human Reject queue is where a spent cap, a fail-closed verdict, and a `split` before Rework exists all land -- never a silent retry. Section 2 orders this hold after its release: the verbs merged in the previous seed, and this ticket's `depends` edge is the enforcement. Section 9 and section 19 pin the queue's shape: a stem awaits a verdict when its latest terminal carries the marker with no later verdict signal; the spine stamps the marker on the terminal it already writes (the routing reads the FINAL cap state, so dispatch precedes the terminal write), and queue code writes no terminal. Section 11.4's pre-daemon default keeps the bootstrap drain headless: an arrival with budget auto-resolves to keep inside the same drain with a machine-actor signal that draws down and never re-arms; at a spent cap the stem reaches a terminal-without-merge and the drain proceeds. Section 13 touchpoint 4 makes the arrival an escalation that, until the Phase 4 notify transport lands, rests in `status` as a journaled signal. This ticket depends on `diagnosis-eval-run` because it is the first consumer of diagnosis verdicts as routing input, and the plan wants the surface's agreement rate recorded before a verdict moves a stem.

## Scope in
A new module `squatch/reject.py` owning the routing predicate and the queue fold. `MARKER` = `reject_queue` (the terminal body's `routed` value), `ARRIVAL` = `reject_queue_arrival` (the escalation name). `route(config, events, stem, outcome, record) -> Routing(routed, reason)` decides in this fixed order over the journal AFTER this recovery's own draws: (1) `caps.spent(config, events, stem)` non-null -- Reject with the spent reason verbatim; (2) the diagnosis `call` is `skipped` -- no marker (the `premise_failed` park and the `budget_exceeded` park keep their own releases); (3) `verdict` null (`invalid_artifact`, or a diagnose call that itself ended `infra_error` or `timeout`) -- Reject, reason `no schema-valid diagnosis verdict`; (4) `reject`, `abandon-human`, or `split` -- Reject, reason naming the verdict (`split` is fail-closed until Rework lands); (5) `retry` or `escalate` -- no marker (pre-ladder, `escalate` re-runs at the authored capability exactly as `spine-diagnosis` left it). `awaiting(events) -> Mapping[str, Arrival]` is the Reject fold: a stem awaits a verdict when its latest terminal `state_transition` carries `routed: reject_queue`, or an `escalation` signal naming `reject_queue_arrival` follows that terminal, with no later `confirm` or `reject` signal of either actor. `squatch/runner.py`'s terminal handler calls `route` after the diagnosis and before the terminal write, puts `routed` and `reject_reason` on the terminal body when set, then journals the arrival as one `signal` with body `kind: escalation`, `escalation: reject_queue_arrival`, `reason`, `run_seq` -- both writes the runner's -- and the stop report names the queue and both verbs. `squatch/drain.py`: eligibility excludes every awaiting stem; the re-offer fold treats an awaiting stem thus: with `caps.spent` null it journals a `confirm` signal with `actor: machine` and reason `auto-keep: retry budget remains` through the runner's signal writer, then re-offers it with one `retry` draw exactly as today; at any spent cap it is never re-offered and the tail reports it under `reject queue:` with the reason and the road `squatch confirm <stem>` (keep, re-arms spent caps) or `squatch reject <stem>` (kill); a parked stem whose latest terminal carries no marker and no arrival but whose cap is now spent (a journal written before this mechanism, a lowered cap, a carried `--parked` set) gets the arrival signal journaled by the drain -- the section 11.2 clause, a signal, never a terminal -- and is reported the same way; the operator's `confirm` then makes it eligible as `reject-verbs` landed. `squatch/status.py` gains a `reject queue` category: stem, reason, arrival timestamp, and the two verbs. `squatch/stages.py` is fenced per the section 19 ownership law as the layer whose outcomes feed the marked terminal; it changes only if the terminal reason the routing records must ride `Delivery`. Tests for every rule above; read `squatch/caps.py`, `squatch/diagnose.py`, and `tests/test_verbs.py` in the worktree (they land with the `depends` and did not exist when this seed was authored).

## Scope out
No escalation ladder: no rung walk, no rung fold, no oscillation or identical-terminal short-circuit, no `routed: ladder` (the next seed). No change to the verbs' semantics, to the cap fold's bound, or to the `premise_bounce` draw as landed. No notify transport: the arrival rests in `status` (section 13 touchpoint 4). No supervised-merge hold, no daemon-era hold of any kind (Phase 6). No new run state, no new Outcome, no new frontmatter field, config key, or cap; `signal` and `state_transition` keep their types and the `routed` value set is exactly `reject_queue` here. No change to `specs/` or `ticket.md`.

## Scope fence
- squatch/reject.py
- squatch/runner.py
- squatch/stages.py
- squatch/drain.py
- squatch/status.py
- tests/test_reject.py
- tests/test_terminal.py
- tests/test_drain.py
- tests/test_drain_upgrade.py
- tests/test_cli.py
- tests/test_verbs.py

## Acceptance criteria
- In `tests/test_reject.py`, `route` returns the marker with the spent-cap reason verbatim for a spent `diagnosis` cap whatever the verdict, no marker for a `skipped` call on `premise_failed`, the marker with reason `no schema-valid diagnosis verdict` for a null verdict, the marker for each of `reject`, `abandon-human`, `split`, and no marker for `retry` and `escalate`.
- In `tests/test_reject.py`, `awaiting` reports a stem whose latest terminal carries the marker, a stem whose latest terminal is unmarked but followed by an arrival signal, and neither once a later `confirm` (operator or machine) or `reject` signal follows.
- In `tests/test_terminal.py`, a run whose diagnosis verdict is `reject` journals its terminal with `routed: reject_queue` and `reject_reason`, then one `escalation` signal naming `reject_queue_arrival` with the run's `run_seq`, in that order, and the stop report line names `squatch confirm` and `squatch reject`; a run whose verdict is `retry` journals a terminal with no `routed` key and no arrival signal.
- In `tests/test_terminal.py`, under config `caps: {infra: 1}` a run ending `infra_error` journals a marked terminal with `reject_reason` exactly `infra cap spent (1 of 1 drawn)` and no diagnose effect.
- In `tests/test_drain.py`, a stem whose latest terminal is marked with `retry` budget remaining is not in the eligible set, is re-offered in the same invocation after one `confirm` signal with `actor: machine` and one `retry` draw, and merges when its re-run is green; a marked stem under config `caps: {retry: 1}` with its unit drawn is never re-offered, the tail prints `reject queue:` naming it with `squatch confirm` and `squatch reject`, and the drain exits 0.
- In `tests/test_drain.py`, a parked stem with an unmarked terminal and a spent `retry` cap gets one arrival signal journaled by the drain and is reported under `reject queue:`; a second drain journals no second arrival for it; after `squatch confirm <stem>` it dispatches as eligible work.
- In `tests/test_drain_upgrade.py`, a carried `--parked` stem that is awaiting a verdict stays excluded from eligibility in the child and is reported under `reject queue:`.
- In `tests/test_cli.py`, `squatch status` lists a marked stem under `reject queue` with its reason and both verbs, and omits it once a `reject` signal follows.
- In `tests/test_verbs.py`, `squatch confirm <stem>` on a marked stem resolves the hold (the next drain dispatches it as eligible) and `squatch reject <stem>` clears it from `status`.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_reject.py -q
uv run pytest tests/test_terminal.py tests/test_drain.py tests/test_drain_upgrade.py tests/test_cli.py tests/test_verbs.py -q
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` if the marker cannot ride the terminal `squatch/runner.py` already writes without a second terminal writer, if the auto-keep cannot reuse the runner's signal writer and the drain's existing retry draw, if the `spine-diagnosis` record as landed cannot supply `call` and `verdict` to `route`, if any file outside the fence must change, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 75m
- stuck: 150m
