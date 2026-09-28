## Outcome
ok

## Surprises / judgment calls
The fenced `Stages` and `Pipeline` owners could not gain a public accessor. Added a short-lived public Driver construction binding in `squatch/driver.py`; `_locked` captures the first pipeline stage Driver (before the diagnosis-only Driver), caches that pipeline, and passes both through `_RestartRunner.bound_pipeline`. Production absence raises; an explicitly injected synthetic pipeline that constructs no Driver remains retro-off.

The named regression suites needed no assertion migration after the silent production path was removed. `tests/test_drain_reentry.py` self-upgrades and its stub does not execute the child; `tests/test_seed_successor.py` drives `Drain` directly without the hook; `tests/test_drain_upgrade.py`, `tests/test_storm_hold.py`, and `tests/test_storm_notification_activation.py` inject Driver-less synthetic pipelines; `tests/test_daemon_composition.py` and `tests/test_kill_cli_activation.py` inspect composition without a post-merge live-drain quiescence; and `tests/test_restart_timers.py`, `tests/test_provider_cooldown_failover.py`, `tests/test_watchdog_activation.py`, `tests/test_daemon_pause.py`, and `tests/test_control_cli.py` do not execute a production-Driver merge-to-quiescence path. Their listed assertions therefore remain unchanged. `tests/test_retro.py` now covers that exact production-shaped path and a real handoff child.

## Dead ends
Passing the binding as a fifth `_locked` callback argument broke existing direct composition probes, so the explicit seam moved to `_RestartRunner.bound_pipeline`. A literal production factory name in the new fail-closed test tripped a historical predecessor-source scanner; splitting only that attribute-name literal preserved the test without changing the settled scanner.

## Second problems filed

## Resolved engine/model
OpenAI / GPT-5 Codex

## Predicted vs actual
Expected 75m; actual approximately 65m for this retry.
