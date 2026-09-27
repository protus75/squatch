---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: high
agent_effort: high
---
## Depends on
- soak-run

## Context
- tickets/soak-run/daemon-soak-report.json
- squatch/artifacts.py
- eval/daemon_soak.py
- tests/test_daemon_soak_runner.py
- tests/test_seeded_phase3_11.py

## Plan contract
- section 20

## Goal
Read-close Phase 3 from committed soak evidence and seed the exact Phase 4
core batch.

## Why
`soak-run` is the report producer and `daemon-soak-runner` is its machinery.
The exit reads that committed custody rather than rerunning or self-attesting
the soak, then makes the plan-defined Phase 4 boundary available.
The regenerated seed runs after the section-20 registry compaction and the
merged predecessor-fixture migration; main is green at this ticket SHA.
It also consumes the repaired Phase 4 composition fences: the ProcessExec
event callback owner and the distinct production notification seam/root.
The section-20 registry keeps its stable predecessor-test delimiter, so the
full inherited suite can verify this regenerated seed.

## Scope in
Implement in order. First, add `tests/test_phase3_exit.py`, a
committed-artifact-only read of `tickets/soak-run/daemon-soak-report.json`.
Validate the report as `DaemonSoakReport` using its owner
`squatch/artifacts.py`, require `injected_hours >= 24`, and require exactly
the closed members `worker_killed_mid_run`, `conflict_resolution_rungs`, and
`semantic_conflict_integration_red`. Each entry must be green, name a
non-empty producing run, carry its expected fault observable, and record the
required disposition: `alert`, `alert`, and `box`, respectively. This test
reads only the committed report: `daemon-soak-runner` is machinery and
`soak-run` is producer. A failed read is `premise_failed`; do not rerun the
soak or write a report.

Second, author only the confirmed Phase 4 core tickets
`watchdog-event-stream`, `notify-transport`, and `phase4-continue`, plus
`tests/test_seeded_phase4_core.py`, as uncommitted ticket-plane output. Both
machinery seeds depend on `phase3-exit`, cite section 20 alone, start
medium/medium, and use budgets within `drain.max_ticket_minutes`.
`watchdog-event-stream` owns new `squatch/watchdog.py`, existing
`squatch/providers.py`, existing `squatch/seams.py`, new
`tests/test_watchdog.py`, and existing `tests/test_providers.py` and
`tests/test_seams.py`, embedding every existing path. `notify-transport` owns
new `squatch/notify.py`, existing `squatch/config.py`, `squatch/seams.py`,
`squatch/serve.py`, `squatch/__main__.py`, new `tests/test_notify.py`, and
existing `tests/test_config.py`, `tests/test_seams.py`, `tests/test_serve.py`.
It embeds config, seams, serve, and the serve test; the CLI root and other two
tests are fenced on-demand headroom exceptions. Its ticket pins the distinct
injectable `Notifications.notify(argv)` seam, private notification
SubprocessExec, separate `_serve` construction, and Serve watcher reconciliation
at startup and each poll, including the unset warning/status-only path.
`phase4-continue` depends on both machinery stems, owns only `tickets` and
new `tests/test_seeded_phase4_01.py`, embeds `tests/test_seeded_phase3_11.py`,
cites section 20 alone, and starts medium/medium.

`phase4-continue` carries exactly this finite ordered Phase 4 suffix:
`watchdog-detector` plus `watchdog-activation`, then
`provider-cooldown-failover` alone, then `reliability-battery`, then
`reliability-run`, then `phase4-exit` alone and last. Its continuations are
`phase4-continue`, then `phase4-continue-02` onward; every nonterminal
admission carries its named payload batch plus the next continuation under the
three-seed cap, and the terminal admission carries only `phase4-exit`.
Do not invent, rename, reorder, add, or omit a Phase 4 payload.

`tests/test_seeded_phase4_core.py` follows the established seeded-test pattern:
it names the exact core batch, ownership fences, dependency edges, Context
closure, new-path owners, section-20-only contracts, the finite ordered suffix,
and authoring-time max-effort `specs/implement.md` render headroom under
`RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM`. Prompt-spec sources with the
engine data-block delimiter, including `squatch/specs.py`, are never Context.

## Scope out
Do not rerun or alter the soak, write or self-attest its report, implement
Phase 4 machinery, author a Phase 4 feature beyond the core batch and its one
continuation, or read a live journal as exit evidence.

## Scope fence
- tickets
- tests/test_phase3_exit.py
- tests/test_seeded_phase4_core.py

## Acceptance criteria
- `tests/test_phase3_exit.py` validates the committed `DaemonSoakReport`, its exact three green disposition-bearing members, injected 24-hour evidence, and producing runs without rerunning the soak.
- `tests/test_seeded_phase4_core.py` pins exactly `watchdog-event-stream`, `notify-transport`, and `phase4-continue`, their `phase3-exit` edges, bounded admission, ticket structure, and closed ownership and Context contracts.
- `tests/test_seeded_phase4_core.py` proves the finite Phase 4 continuation, excludes delimiter-bearing Context, and proves each max-effort render fits requisition headroom.

## Verification
```
uv run pytest tests/test_phase3_exit.py tests/test_seeded_phase4_core.py -q
uv run pytest -q
```

## Definition of rejected
Reject a self-attested or rerun report, a missing producer or machinery
custody, an uncommitted-artifact exit read, a Phase 4 seed outside the core
batch and continuation, delimiter-bearing Context, or a render that exceeds
headroom.

## Time budget
- expected: 75m
- stuck: 150m
