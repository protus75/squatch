---
state: confirmed
source: seed
priority: P1
kind: feature
agent_tier: high
agent_effort: high
---
## Depends on
- phase4-exit

## Context
- squatch/driver.py
- squatch/git.py
- squatch/box.py
- tests/test_seeded_phase4_02.py

## Plan contract
- section 20

## Goal
Run governed retros from the live drain and commit each validated report directly
to the reserved main-checkout report lane.

## Why
The retro window must observe the production journal and run under the same
provider, cooldown, effect, and writer-lock rules as ticket stages without
turning reports into ordinary worktree artifacts.

## Scope in
Add `squatch/retro.py`, `specs/retro.md`, and `tests/test_retro.py`. Define a
closed local `RetroArtifact` and its Markdown renderer in `squatch/retro.py`.
Run an `LLMStage` named `retro`, rendered from `specs/retro.md`, through the
existing `Driver` and the lock-held session's shared provider/cooldown payload.
The artifact stays local: do not register it in `squatch/artifacts.py` or
`squatch/stages.py`, and it is not a JSON artifact.

Under the drain's already-held writer lock, write the validated Markdown receipt
directly in MAIN as `tickets/retro/<seq>.md`, with a zero-padded sequence and
the reserved `retro` directory remaining a non-stem. Commit it through the
existing ticket-plane Git/Effects seam, never the ordinary worktree OUTBOX
artifact lift. The commit effect key is exactly `retro/<seq>` and its
`effect_completion` is the completed retro-window boundary.

Add a default-off retro hook to `Drain`. Bind it in
`squatch/__main__.py::_drain` with the main repo, journal, injected clock and
filesystem, Git/Effects, Box, existing Driver, and shared session payload. Every
self-upgraded CLI child rebinds the hook. Expose the Driver through an explicit
public read-only accessor on the composed production pipeline or Stages and pass
the pipeline and Driver through an explicit construction seam; do not probe
private `_retro_pipelines`, `_retro_prebuilt`, or `_driver` attributes. If
production hook construction is requested without a Driver, raise named
`RetroConstructionError` with a paved road rather than returning `False` or
silently disabling retro. At the top of every dispatch iteration,
before the next ticket dispatch, perform an UNFORCED due check. Run only when
the current window has N=25 merged tickets, is M=7 days old, or one exact signal
kind reaches S=5: a used non-empty `gate_bypass`, a Rework invocation/order, a
terminal `state_transition` with `to: gate_failed`, or an admission whose conflict
facts include integration-red implicated paths.

Run one FORCED retro at quiescence and immediately before dispatching any
phase-exit ticket, only if a merge landed after the latest completed
`retro/<seq>` report. Success commits exactly one report and advances the
window boundary. On failure append one `signal` keyed
`retro-failed/<window-boundary>/<trigger>` with body exactly
`{kind: retro_failed, window_boundary, trigger, error_code}`, enqueue exactly one
signature-deduped `failure_report` carrying that identity and a bounded redacted
summary, and suppress all further due or forced attempts in that window. Only a
later `retro/<seq>` effect completion releases suppression.

The fenced measured on-demand inspection exceptions are `squatch/drain.py`,
`squatch/__main__.py`, `tests/test_drain.py`, `tests/test_driver.py`,
`tests/test_box.py`, `tests/test_drain_reentry.py`,
`tests/test_drain_upgrade.py`,
`tests/test_daemon_composition.py`, `tests/test_kill_cli_activation.py`,
`tests/test_storm_hold.py`, `tests/test_storm_notification_activation.py`,
`tests/test_restart_timers.py`, `tests/test_provider_cooldown_failover.py`,
`tests/test_watchdog_activation.py`, `tests/test_daemon_pause.py`, and
`tests/test_control_cli.py`.

Treat those suites as a transition-risk fence, not as a claim that each existing
scenario fires retro. Migrate only actual forced post-merge fallout: the
ancestry-history assertion in `tests/test_drain_upgrade.py`; the fake-call and spawned-main history assertions
in `tests/test_daemon_composition.py` and `tests/test_kill_cli_activation.py`;
the ordered pipeline-call and control-journal assertions in
`tests/test_storm_hold.py`; the trip/report Box-count assertions in
`tests/test_storm_notification_activation.py`; the process-call and
cooldown-journal sequences in `tests/test_restart_timers.py` and
`tests/test_provider_cooldown_failover.py`; the provider/notification call lists
in `tests/test_watchdog_activation.py`; the dispatch-call/snapshot and
pause-journal assertions in `tests/test_daemon_pause.py`; and the drain result
and control-journal assertions in `tests/test_control_cli.py`. Preserve every
unrelated dispatch, re-entry, upgrade, control, storm, provider, watchdog, and
daemon assertion.
Record a concrete non-firing reason when a fenced scenario does not cross the
forced boundary: `tests/test_drain_reentry.py` uses `NoHandoff`;
`tests/test_drain_upgrade.py` has a stubbed handoff; kill scenarios stop first;
provider cooldown ends `premise_failed`; and daemon-pause/control scenarios have
no tickets. Keep `tests/test_seed_successor.py` unchanged and outside the fence
because it calls `Bench.drain()` directly, for which the hook remains default-off.

## Scope out
Do not add an artifact registry entry, a second provider client, an OUTBOX
report, a retro ticket stem, another trigger, or an unbounded retry loop. Do not
change behavior of direct `Drain` constructions that omit the hook.

## Scope fence
- squatch/retro.py
- specs/retro.md
- tests/test_retro.py
- squatch/drain.py
- squatch/driver.py
- squatch/__main__.py
- squatch/box.py
- tests/test_drain.py
- tests/test_driver.py
- tests/test_box.py
- tests/test_drain_reentry.py
- tests/test_drain_upgrade.py
- tests/test_daemon_composition.py
- tests/test_kill_cli_activation.py
- tests/test_storm_hold.py
- tests/test_storm_notification_activation.py
- tests/test_restart_timers.py
- tests/test_provider_cooldown_failover.py
- tests/test_watchdog_activation.py
- tests/test_daemon_pause.py
- tests/test_control_cli.py

## Acceptance criteria
- `tests/test_retro.py` proves the closed local artifact, `retro` LLMStage and prompt, shared Driver/provider path, validated Markdown rendering, and absence of artifact-registry or second-client behavior.
- `tests/test_retro.py` drives the production `_drain` path end to end and proves merge then quiescence commits exactly one `tickets/retro/000001.md` on main with effect key `retro/000001` while the writer lock is held.
- `tests/test_retro.py` proves the public Driver accessor, explicit construction seam, named fail-closed `RetroConstructionError`, default-off direct Drain hook, and rebinding through the existing self-upgrade handoff path with an executing child.
- `tests/test_retro.py` proves the exact N=25, M=7-day, and S=5 unforced checks, both forced boundaries with merge-since-report gating, one-report window advancement, and exact window-suppressed failure signal and Box route with no unbounded retry.
- `tests/test_retro.py` and every named regression suite prove that an actually reached forced retro changes only its listed scripted-call, Box, journal, or main-history assertion, while a non-firing scenario stays unchanged for its concrete reason and retains all other behavior.
- `uv run pytest -q` proves the full predecessor suite remains green.

## Verification
```
uv run pytest tests/test_retro.py tests/test_drain.py tests/test_driver.py tests/test_box.py tests/test_drain_reentry.py tests/test_drain_upgrade.py tests/test_daemon_composition.py tests/test_kill_cli_activation.py tests/test_storm_hold.py tests/test_storm_notification_activation.py tests/test_restart_timers.py tests/test_provider_cooldown_failover.py tests/test_watchdog_activation.py tests/test_daemon_pause.py tests/test_control_cli.py -q
uv run pytest -q
```

## Definition of rejected
Reject an OUTBOX or JSON report, an unguided model call, an unbound production
hook, a non-exact trigger, a forced run without a new merge, duplicate failure
messages, retry looping in a suppressed window, or an unnamed regression edit.

## Time budget
- expected: 75m
- stuck: 150m
