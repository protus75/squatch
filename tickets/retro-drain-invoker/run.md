## Outcome
ok

## Surprises / judgment calls
The regenerated ticket and section 20 corrected the prior attempt's false successor premise: tests/test_seed_successor.py is now explicitly outside the fence because its direct Bench.drain() construction remains default-off. The production `_drain` path binds retro unconditionally, captures the first pipeline Driver through the public read-only DriverBinding accessor, and fails closed with RetroConstructionError when that explicit seam supplies no Driver. Retro, its Effects/Box dependencies, and specs/retro.md are constructed once at bind time; the per-boundary callback only calls Retro.run, so attempt failures take the exact retro_failed signal and failure_report route.

Regression disposition: tests/test_drain.py now gives scripted CLI pipelines a governed Driver and directly asserts the retro call/report after a reached quiescence boundary. tests/test_drain_upgrade.py binds that Driver; stubbed self-upgrade handoffs still do not execute a child, while the later premise-release scenario reaches quiescence and now asserts the retro call and final main-history commit. tests/test_daemon_composition.py and tests/test_restart_timers.py bind a Driver, but their relevant scripted outcomes remain premise_failed and do not force retro. tests/test_storm_hold.py asserts its ordered dispatch/control scenarios also make exactly one retro call after the merges. tests/test_storm_notification_activation.py preserves the one trip/one storm-report Box count and asserts the subsequent retro call. tests/test_watchdog_activation.py teaches the existing provider process about the retro surface and migrates only drain call lists; notification assertions remain unchanged. tests/test_drain_reentry.py remains unchanged because NoHandoff does not execute the child. tests/test_kill_cli_activation.py remains unchanged because kill stops before a qualifying boundary. tests/test_provider_cooldown_failover.py remains unchanged because the resumed fixture ends premise_failed. tests/test_daemon_pause.py and tests/test_control_cli.py remain unchanged because their CLI composition scenarios have no tickets. tests/test_driver.py and tests/test_box.py required no assertion changes and remain green.

## Dead ends
Restoring the prior implementation with unconditional binding first exposed 61 scripted drain failures because those pipeline factories constructed no Driver. Adding one explicit test-fixture binding seam resolved that without restoring the rejected retro_enabled path. The first watchdog migration still produced retro_failed in the directory-stream fixture because its process assumed every model call carried an active watchdog stdout callback; allowing the ticketless retro call to use the same process without that callback produced the validated report and preserved the streaming assertions.

Both Verification commands passed exactly as written: the focused command passed 212 tests, and `uv run pytest -q` passed 1379 tests.

## Second problems filed

## Resolved engine/model
OpenAI / GPT-5 Codex.

## Predicted vs actual
Expected: 75m. Actual: approximately 35m, including prior-attempt recovery, regression migration, two exact verification runs, and the full-suite audit.
