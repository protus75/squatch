---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: medium
agent_effort: medium
---
## Depends on
- merge-queue-activation
- rework-activation

## Context
- tests/test_seeded_phase3_core.py
- squatch/daemon.py
- squatch/watcher.py
- squatch/scheduler.py
- squatch/triage.py
- squatch/box.py
- squatch/rework.py
- squatch/__main__.py
- tests/test_daemon_composition.py
- tests/test_mergequeue.py

## Plan contract
- section 20

## Goal
Author the background-consumer and control-inbox seeds and the next shrinking Phase 3 continuation.

## Why
The queue and Rework compositions are established; task lifetime ownership and durable request intake are the next independent boundaries.

## Scope in
Author exactly `tickets/background-consumers/ticket.md`, `tickets/control-inbox/ticket.md`, and `tickets/phase3-continue-08/ticket.md` as uncommitted confirmed seeds, plus committed `tests/test_seeded_phase3_07.py`. background-consumers depends on phase3-continue-07; control-inbox depends on background-consumers; phase3-continue-08 depends on both deliverables. All three cite section 20 alone, use medium/medium and expected/stuck budgets 75m/150m.

background-consumers owns the watcher, merge/Rework and box task lifetimes in daemon.py, proved by its new tests/test_daemon_tasks.py. Define one explicit in-process owner over three injected awaitable callbacks; daemon.py owns their repetition and lifetime, while callback construction remains deferred. The watcher callback supplies one priority snapshot to the existing `Watcher.observed` adapter; the merge callback consumes one post-admission handoff through the already composed Rework path with its SHA supplied by the callback; the box callback performs one existing `Triage.run` pass. The owner starts all three callback loops, awaits them on shutdown, and observes cancellation. If one callback raises, the owner's shutdown await re-raises that exception after cancelling and awaiting the remaining tasks. Require one independently named test per consumer lifetime plus tests for clean shutdown, cancellation, and sibling cleanup on exception. No new observation source, SHA source, Triage composition, or consumer policy is invented in this ticket: those are injected callbacks. It owns no typed inbox module or request policy. control-inbox owns the typed, durable file-backed request inbox in squatch/control.py and its tests/test_control.py. It hooks daemon.py to consume under the lock-held journal: crash-safe request publication, restart-unique lifecycle and hold-instance identity, exactly-once consumption and a decision journaled before governed mutation. Stale-lifecycle requests and releases predating a hold cannot affect later identities. Prove replay at crash points; do not activate pause/kill CLI verbs in this pair.

Use this exact Context map for the emitted seeds, preserving ordering. Sibling-new files stay outside every Context even when dependencies order their eventual implementation. phase3-continue-08 includes tests/test_mergequeue.py as the compact existing predecessor surface for pause/hold activation, plus the established seeded-test pattern; section 20 permits omitting the redundant mergequeue implementation when the registry plus that test establish the authoring contract. Do not replace the pattern with a not-yet-merged numbered test.
```yaml
context:
  background-consumers:
    - squatch/daemon.py
    - squatch/watcher.py
    - squatch/scheduler.py
    - squatch/triage.py
    - squatch/box.py
    - squatch/rework.py
    - tests/test_daemon_composition.py
  control-inbox:
    - squatch/daemon.py
    - tests/test_daemon_composition.py
  phase3-continue-08:
    - tests/test_seeded_phase3_core.py
    - squatch/daemon.py
    - squatch/__main__.py
    - tests/test_daemon_composition.py
    - tests/test_mergequeue.py
```

The keyed ownership record below is exact; each emitted fence is its owns followed by hooks, except the authoring continuation's directory entry remains tickets. background-consumers owns only tests/test_daemon_tasks.py and hooks daemon.py. control-inbox owns squatch/control.py and tests/test_control.py and hooks daemon.py and tests/test_daemon_tasks.py.
```yaml
ownership:
  background-consumers:
    owns:
      - tests/test_daemon_tasks.py
    hooks:
      - squatch/daemon.py
  control-inbox:
    owns:
      - squatch/control.py
      - tests/test_control.py
    hooks:
      - squatch/daemon.py
      - tests/test_daemon_tasks.py
  phase3-continue-08:
    owns:
      - tickets
      - tests/test_seeded_phase3_08.py
    hooks: []
```

Only `squatch/control.py`, `tests/test_daemon_tasks.py`, `tests/test_control.py` and `tests/test_seeded_phase3_08.py` are new at authoring; pin that exact `NEW_AT_AUTHORING` set.

Pin an EXISTING_AT_AUTHORING map of actual sizes when this continuation is authored, including the then-merged daemon, watcher/scheduler, triage/box, Rework, CLI and composition/predecessor-test evidence named in the Context map. Require set(context) <= EXISTING_AT_AUTHORING and every existing fenced file in Context; classify the new files by their registry owners even after later merges. The configured limits are pinned observably as seeding cap 3 and `drain.max_ticket_minutes` 180, while the generated test still loads config to prove the live values. Synthetic renders use only pinned authoring-time sizes, never later live bytes or existence checks. Exclude all delimiter-carrying prompt-spec sources, including squatch/specs.py.

For the pause pair that `phase3-continue-08` will author, pin this exact ownership record and derive each seed fence as owns followed by hooks. The boundary owns its new test and hooks every existing daemon/control predecessor test it can affect. The activation additionally hooks the production composition harness and all merge/CLI predecessor surfaces it migrates.
```yaml
pause_ownership:
  dispatch-pause-boundary:
    owns:
      - tests/test_daemon_pause.py
    hooks:
      - squatch/daemon.py
      - squatch/control.py
      - tests/test_daemon_tasks.py
      - tests/test_control.py
  pause-resume-activation:
    owns:
      - tests/test_control_cli.py
    hooks:
      - squatch/daemon.py
      - squatch/control.py
      - squatch/mergequeue.py
      - squatch/__main__.py
      - tests/test_daemon_pause.py
      - tests/test_mergequeue.py
      - tests/test_daemon_composition.py
  phase3-continue-09:
    owns:
      - tickets
      - tests/test_seeded_phase3_09.py
    hooks: []
```
The next continuation must pin exact emitted identities and dependency edges (`dispatch-pause-boundary` depends on `phase3-continue-08`; `pause-resume-activation` depends on that boundary; `phase3-continue-09` depends on both), confirmed seed status, medium/medium tiers, 75m/150m budgets, the configured seeding cap, every existing fence path in Context, the exact new-path owners, max-effort render headroom, and successor suffix equality. It must migrate the actual dormancy contracts in `tests/test_daemon_composition.py`, `tests/test_daemon_pause.py`, and `tests/test_mergequeue.py`, while running `tests/test_daemon_tasks.py` and `tests/test_control.py` unchanged in Verification as preservation-only suites outside the activation fence and Context. The activation seed includes the then-existing composition harness and fenced predecessor tests in its own Context. `squatch/__main__.py` is existing Context for the CLI activation. Sibling-new paths remain outside this continuation ticket's own Context, but after their owning dependencies merge they are existing Context for the pause seeds.

control-inbox fences `tests/test_daemon_tasks.py` as a hook and runs it in Verification, keeping it out of Context because it is sibling-new. Both deliverable seeds preserve `tests/test_daemon_composition.py` unchanged and run it in Verification. Require tests/test_seeded_phase3_07.py to assert those exact predecessor-test closure requirements, the Context map and ownership records above, and the new-path owners. Their fences must not invalidate any predecessor outside these allowed edits.

The finite ordered admissions this continuation carries are:
```yaml
- [background-consumers, control-inbox]
- [dispatch-pause-boundary, pause-resume-activation]
- [kill-signal-journal, kill-executor-abort]
- [kill-worker-stop, kill-failure-suppression]
- [kill-cli-activation]
- [heartbeat]
- [restart-timers]
- [flake-detection, flake-release]
- [journal-roll, storm-ledger]
- [storm-producer-wiring, storm-notification-activation]
- [storm-dispatch-hold]
- [checkpoint-push]
- [daemon-soak]
- [soak-run]
- [phase3-exit]
```
The successor phase3-continue-08 carries:
```yaml
- [dispatch-pause-boundary, pause-resume-activation]
- [kill-signal-journal, kill-executor-abort]
- [kill-worker-stop, kill-failure-suppression]
- [kill-cli-activation]
- [heartbeat]
- [restart-timers]
- [flake-detection, flake-release]
- [journal-roll, storm-ledger]
- [storm-producer-wiring, storm-notification-activation]
- [storm-dispatch-hold]
- [checkpoint-push]
- [daemon-soak]
- [soak-run]
- [phase3-exit]
```

## Scope out
Do not implement either boundary, author beyond phase3-continue-08, change production code, repeat the activation pair, or put sibling-new paths or delimiter-bearing prompt-spec sources in Context. Typed-inbox construction belongs only to control-inbox; background-consumers must be independently proved on task lifetimes.

## Scope fence
- tickets
- tests/test_seeded_phase3_07.py

## Acceptance criteria
- `tests/test_seeded_phase3_07.py` proves the exact three identities, dependency edges, confirmed seed status, medium/medium tiers, 75m/150m budgets and the configured seeding cap, plus exact fences and keyed owns/hooks matching the registry split above.
- `tests/test_seeded_phase3_07.py` pins the exact per-seed Context map, EXISTING_AT_AUTHORING sizes and exact four-path NEW_AT_AUTHORING set; every existing fence entry is Context, all Context paths are in the pinned map and exclude delimiter-carrying sources. It names background-consumers as tests/test_daemon_tasks.py's owner and control-inbox as squatch/control.py and tests/test_control.py's owner; phase3-continue-08 owns its numbered test.
- `tests/test_seeded_phase3_07.py` proves control-inbox fences tests/test_daemon_tasks.py as a hook and runs it in Verification without listing it in Context; both deliverables preserve tests/test_daemon_composition.py unchanged and run it in Verification. It pins tests/test_mergequeue.py in phase3-continue-08 Context with its authoring-time size and keeps all sibling-new files outside Context.
- `tests/test_seeded_phase3_07.py` pins the concrete watcher-snapshot, Rework-handoff and Triage-pass callback boundaries, independently observable task lifetimes, cancellation, and exception propagation; it pins `squatch/watcher.py`, `squatch/scheduler.py`, `squatch/triage.py`, `squatch/box.py`, and `squatch/rework.py` as read-only background-consumer Context.
- `tests/test_seeded_phase3_07.py` pins `squatch/__main__.py` in phase3-continue-08 Context and requires that continuation to carry the exact pause-pair ownership, fences, edges, tier/effort, budgets, cap, predecessor-test closure, authoring-time size map, render headroom, and shrinking suffix stated above.
- `tests/test_seeded_phase3_07.py` proves max-effort synthetic renders using the pinned Context sizes remain within RENDER_BOUND_CHARS["max"] * REQ_RENDER_HEADROOM, and pins both exact suffix lists with successor == full[1:].
- `uv run pytest -q` exits 0.

## Verification
```
uv run pytest tests/test_seeded_phase3_07.py -q
uv run pytest -q
```

## Definition of rejected
Stop if either boundary cannot be proved independently, predecessor-test closure requires a path outside the registry fence, any Context names a sibling-new file, a seed exceeds requisition headroom, or the successor duplicates this admission instead of shrinking the suffix.

## Time budget
- expected: 75m
- stuck: 150m
