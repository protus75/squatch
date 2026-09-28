## Outcome
ok

## Surprises / judgment calls
The corrected fence made the explicit Driver route possible without the prior attempt's context-variable capture. `Stages.driver` is now the read-only public accessor; the production retro seam composes one dedicated pipeline per lock-held drain session, reads that accessor, and leaves Runner's ticket pipeline factory fresh on every dispatch.

Regression disposition: `tests/test_drain.py` gained fixture-only `stages.driver` plumbing while its parent/child ordering test and assertions stayed unchanged. `tests/test_drain_upgrade.py` gained the same plumbing; its stubbed handoff still does not execute a child, and its premise-failed scenario stayed unchanged. `tests/test_daemon_composition.py` and `tests/test_restart_timers.py` gained fixture plumbing, but their scripted drains end `premise_failed`, so no forced retro fires. `tests/test_storm_hold.py` migrated only the ordered call assertions for the reached post-merge retro; `tests/test_storm_notification_activation.py` preserved the trip/report Box counts and added the reached retro call; `tests/test_watchdog_activation.py` migrated the provider call lists and process fixture for the retro surface while preserving notification and watchdog assertions. `tests/test_drain_reentry.py` remained unchanged because `NoHandoff` never executes the child. `tests/test_kill_cli_activation.py` remained unchanged because kill stops before a qualifying boundary. `tests/test_provider_cooldown_failover.py` remained unchanged because its drain ends `premise_failed`. `tests/test_daemon_pause.py` and `tests/test_control_cli.py` remained unchanged because their scenarios have no tickets. `tests/test_driver.py`, `tests/test_box.py`, and `tests/test_stages.py` required no regression changes and remained green; the new public accessor is proved in `tests/test_retro.py`.

## Dead ends
The first full-suite run exposed direct non-drain `_RestartRunner` constructions in the shakeout and daemon-soak harnesses. Making the explicit retro-pipeline constructor optional for those default-off users preserved their established path; requesting production retro without that seam still raises `RetroConstructionError`. After that correction, both Verification commands passed exactly as written: the focused command passed 272 tests and the full suite passed 1383 tests.

## Second problems filed

## Resolved engine/model
OpenAI / GPT-5 Codex.

## Predicted vs actual
Expected: 75m. Actual: approximately 30m, including prior-attempt recovery, regression migration, and two complete Verification runs.
