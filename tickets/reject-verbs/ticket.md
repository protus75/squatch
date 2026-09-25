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
- suggestion-box

## Context
- squatch/__main__.py
- squatch/runner.py
- squatch/drain.py
- squatch/tickets.py
- squatch/artifacts.py
- tests/test_cli.py
- tests/test_drain.py
- tests/test_drain_upgrade.py
- tests/test_terminal.py

## Plan contract
- section 13
- section 11
- section 9
- section 20

## Goal
The two Reject-queue verdict verbs exist before any hold can fire: `squatch confirm <stem>` (the draft->confirmed flip, or keep: re-enqueue with spent spine caps re-armed) and `squatch reject <stem>` (kill: `rejected` stamped, dead-dependency events and per-dependent `failure_report` messages filed inline), both resolving the stem against the journal identity; the `premise_bounce` cap joins the vocabulary with its draw on every `premise_failed` terminal; and the cap fold is bounded by the operator's latest keep.

## Why
Section 2: a hold ships with its release, and its paved road never names an unbuilt verb. The Reject queue (the next seed) is a hold whose releases are exactly these verbs, so they land first, in their own reviewed diff, and the queue's `depends` edge guarantees the order. Section 13 touchpoint 3 fixes the verb mapping and the double-confirm refusal (an unchanged ticket re-fed to freshly reset caps is an infinite cap refill), section 11.2 makes the operator's keep the ONE cap re-arm and bounds the fold by it, and section 9 puts the dead-dependency handling with its trigger: pre-daemon the `reject` verb emits the events and the per-dependent reports inline at the kill, into the box the previous seed built. The `premise_bounce` cap lands here because section 11.1 says every non-ok terminal draws a NAMED budget and a `premise_failed` park at a spent cap must have a reachable release -- the keep this ticket ships -- before the queue that routes a spent cap lands. Section 20: with no engine process running, each verb takes the lock itself; a drain holding it refuses the verb, never a second writer.

## Scope in
`squatch/__main__.py` gains `confirm <stem>` and `reject <stem>`, both composed like `run` through `Runner.session()` (lock, journal, reconcile, intake) and exiting under the section 18 contract: 0 applied, 2 refused. `squatch/runner.py` owns both resolutions -- the verbs' journal writes go through the terminal-write owner, never a second writer -- and the closed constants `VERDICT_SIGNALS` = `confirm | reject` and `ACTORS` = `operator | machine`. Every verdict is one `signal` event with body `kind` (the verb), `actor`, `ticket_sha` (the blob sha of the committed `tickets/<stem>/ticket.md`, or null for a dirless stem), `run_seq` (the stem's latest, or null), and `reason`. Both verbs resolve the stem against the JOURNAL: a stem with no journal event at all is refused ("no journal identity; intake or author it first"), and a stem whose ticket dir is gone is still resolvable. `Runner.confirm(stem)`: a merged stem is refused; a committed `state: draft` ticket is the touchpoint-2 flip -- `state: confirmed` stamped and committed through the ticket-plane lane with `source` kept, then the signal; otherwise it is the keep -- refused as the double-confirm when the stem's latest operator `confirm` signal carries the same `ticket_sha` as now, paved road exactly `edit the ticket (or fix the plan and regenerate it) before re-enqueueing`, else the signal is journaled and the report names the re-enqueue; a stem that is confirmed, never run, and not awaiting anything is refused as nothing to confirm. `Runner.reject(stem)`: a merged stem is refused; otherwise the `reject` signal, then a `state_transition` with `to: rejected` (already in `TERMINAL_RUN_STATES`), then -- when the ticket dir exists -- `state: rejected` stamped into `tickets/<stem>/ticket.md` and committed by pathspec through the ticket-plane lane without re-linting it (a kill never asks the ticket to be valid); a dirless ghost is journal-only. Then the dead-dependency handling, inline: for every committed unmerged ticket whose `Depends on` names the stem, one `signal` with body `kind: dead_dependency`, `dead` (the killed stem), `dependent`, and one `failure_report` enqueued into the box (`origin` the killed stem, `summary` naming the dependent and the kill, `detail` the paved road: re-wire, re-scope, or `squatch reject <dependent>`), the count reported. `squatch/tickets.py`: the lane commit step of `Intake.commit` (add, pathspec commit, intake signal) is factored so the flip and the stamp call the one lane, never a second commit path. `squatch/caps.py` (read it in the worktree: it lands with `spine-caps`): `premise_bounce` joins the served vocabulary and `spent` -- reason `premise_bounce cap spent (<drawn> of <budget> drawn)` -- and the lineage fold gains its bound: draws journaled before the stem's latest `confirm` signal with `actor: operator` fall out of every cap's count; a `confirm` with `actor: machine` never bounds it. `squatch/runner.py`'s terminal handler draws one `premise_bounce` unit through the `cap_consumed` writer on every `premise_failed` terminal, after harvest and before the terminal write, beside the `infra` draw. `squatch/drain.py`: a stem whose latest event among its terminal transitions and its operator `confirm` signals is the confirm is ELIGIBLE (re-enqueued: it runs ahead of re-offers and draws nothing) -- the `premise_failed` park included, since edit-then-confirm is touchpoint 3's edit; a `premise_failed` stem whose `premise_bounce` cap is spent is NOT released by a ticket edit alone -- its parked line names the spent cap and the release `squatch confirm <stem>` after the edit; a blocked stem whose unmerged dependency is `rejected` is reported `blocked ... (dead: <stem>)`; the spent-retry road line names `squatch confirm <stem>` as the re-arm. Tests for every rule above; read `squatch/box.py` in the worktree for the enqueue API (it lands with `suggestion-box`).

## Scope out
No Reject queue, no `routed: reject_queue` marker, no arrival escalation, no awaiting-verdict eligibility fold, no auto-keep (all the next seed): this ticket lands the release before the hold. No escalation ladder, no rung reset semantics beyond the fold bound. No supersedes map (Rework, Phase 3): dead-dependency resolution is over direct `Depends on` edges only. No `kill`, `pause`, `resume` verbs, no control inbox: with no engine process running each verb takes the lock itself, and a held lock is a refusal. No new frontmatter field, config key, cap name beyond `premise_bounce` (already in the `caps:` block), or journal event type. No change to `specs/`, to `ticket.md` beyond the two stamps, or to the merge admission.

## Scope fence
- squatch/__main__.py
- squatch/runner.py
- squatch/tickets.py
- squatch/caps.py
- squatch/drain.py
- tests/test_verbs.py
- tests/test_caps.py
- tests/test_terminal.py
- tests/test_drain.py
- tests/test_drain_upgrade.py
- tests/test_cli.py

## Acceptance criteria
- In `tests/test_verbs.py`, `squatch confirm <stem>` on a committed `state: draft` ticket commits `state: confirmed` through the ticket-plane lane with `source` unchanged, journals one `confirm` signal with `actor: operator` and the ticket blob sha, and exits 0; the next drain runs it.
- In `tests/test_verbs.py`, `squatch confirm <stem>` on a stem parked `gate_failed` journals the keep signal and exits 0; a second `confirm` with no `ticket.md` change is refused (exit 2) with the paved road `edit the ticket (or fix the plan and regenerate it) before re-enqueueing`, and after a ticket edit is committed a third `confirm` is accepted.
- In `tests/test_verbs.py`, `squatch confirm <stem>` and `squatch reject <stem>` on a stem with no journal event are refused (exit 2) naming the missing identity, on a merged stem are refused, and `squatch reject <stem>` on a stem whose ticket dir was removed still journals `reject` and `to: rejected` and exits 0.
- In `tests/test_verbs.py`, `squatch reject <stem>` on a parked stem with two committed dependents journals, in order, the `reject` signal, the `to: rejected` transition, two `dead_dependency` signals naming each dependent, and leaves `tickets/<stem>/ticket.md` committed with `state: rejected` and two pending `failure_report` messages under `<state_dir>/box/` with `origin` the killed stem.
- In `tests/test_verbs.py`, while another process holds the lock both verbs are refused with exit 2 and write nothing.
- In `tests/test_caps.py`, `spent` returns exactly `premise_bounce cap spent (2 of 2 drawn)` for a stem with two `premise_bounce` draws under the shipped defaults, and a stem with three `retry` draws followed by an operator `confirm` signal has `retry` drawn 0 while the same three draws followed by a machine `confirm` signal have `retry` drawn 3.
- In `tests/test_terminal.py`, a run ending `premise_failed` journals one `cap_consumed` with body `cap: premise_bounce`, `ticket_sha`, and `run_seq` before its terminal `state_transition`, and a run ending `gate_failed` journals no `premise_bounce` draw.
- In `tests/test_drain.py`, a stem parked `gate_failed` with an operator `confirm` signal after its terminal dispatches as ELIGIBLE work ahead of any re-offer and draws no retry unit; a `premise_failed` stem under config `caps: {premise_bounce: 1}` with one draw is not released by a ticket edit alone and its parked line contains `premise_bounce cap spent (1 of 1 drawn)` and `squatch confirm`; the same stem after `squatch confirm <stem>` runs in the next drain.
- In `tests/test_drain.py`, a confirmed ticket depending on a `rejected` stem is reported `blocked` with `dead:` naming it and never dispatches.
- In `tests/test_drain_upgrade.py`, the Phase 1 premise-park regression is advanced to the shipped `premise_bounce` contract: the terminal draw is asserted, while ticket edit plus operator confirmation remains the release.
- In `tests/test_cli.py`, every Phase 1 and batch 1-3 claim still passes with the two verbs registered.
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_verbs.py tests/test_caps.py -q
uv run pytest tests/test_terminal.py tests/test_drain.py tests/test_cli.py -q
uv run python -m squatch confirm --help
uv run python -m squatch reject --help
uv run pytest -q
```

## Definition of rejected
Stop and answer `premise_failed` if the verbs cannot journal through `squatch/runner.py` without a second signal writer, if the intake lane in `squatch/tickets.py` cannot be factored so the flip and the stamp share its one commit step, if the `premise_bounce` draw cannot sit in the terminal handler beside the `infra` draw as landed, if any file outside the fence must change, or if `uv run pytest -q` is red on the base commit before any edit.

## Time budget
- expected: 60m
- stuck: 120m
