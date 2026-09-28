## Outcome
premise_failed

## Surprises / judgment calls
The plan status was checked before editing: section 20 specifies the intended runtime, but its regression-migration premise is false on base 52d65256ac433c5c7e08fcd5d6fe4ddbe72e8926. It describes tests/test_seed_successor.py as a main(["drain"]) caller. That suite instead invokes Bench.drain() (line 147); eval/shakeout/bench.py constructs a direct Drain without a hook (lines 100-103) and invokes it directly (lines 168-170). The ticket explicitly preserves default-off direct Drain constructions. Therefore enabling a forced retro in this suite requires changing eval/shakeout/bench.py, outside the fence, or changing the suite's harness beyond its allowed ticket-path main-history assertion. The plan and ticket need an authoring correction before implementation.

The same migration restriction affects tests/test_drain_reentry.py: its successful engine-code merge hands off to NoHandoff, which returns 0 without executing the upgraded child. No quiescence or phase-exit forced boundary is reached after that merge. Adding a scripted model answer alone cannot make the forced retro fire; executing the child or changing the fixture topology exceeds the listed answer-count migration. Running a retro at handoff would introduce an unauthorized trigger.

## Dead ends
Reviewed and temporarily restored the prior attempt's implementation, removed retro_enabled, bound the hook unconditionally, and constructed Retro/spec once in retro_factory. Scripted dispatch fixtures lacking a Driver needed additional construction plumbing, beyond merely changing assertions. The exact first Verification command then passed all 213 tests, but this did not satisfy the required regression evidence: the successor harness remained default-off, and the re-entry harness still skipped the child. Passing checks cannot substitute for the contract. Removed every temporary implementation/test edit after confirming the authoring defect in HEAD. On the restored untouched base, uv run pytest tests/test_seed_successor.py tests/test_drain_reentry.py -q passed (9 tests). No code or ticket change was committed; the branch remains at its original base. The full Verification suite was not run because the contract cannot be satisfied within the permitted migration scope.

Regression inspection: tests/test_seed_successor.py and tests/test_drain_reentry.py have the blockers above. tests/test_drain_upgrade.py also uses a stubbed handoff and needed a Driver in its scripted factory. tests/test_daemon_composition.py and tests/test_restart_timers.py contain injected FakePipeline constructions without a Driver. tests/test_storm_hold.py and tests/test_storm_notification_activation.py inherit the Scripted factory from tests/test_drain.py. tests/test_watchdog_activation.py reaches forced retro, but its existing model process/configuration does not supply a retro response. tests/test_provider_cooldown_failover.py's resumed fixture ends premise_failed rather than merged; tests/test_kill_cli_activation.py stops in-flight or paused work; tests/test_daemon_pause.py's CLI composition case has no tickets; tests/test_control_cli.py's drain lifecycle case has no tickets. No listed regression migration is claimed as delivered.

## Second problems filed

## Resolved engine/model
OpenAI / GPT-6 (Codex); exact serving variant unavailable.

## Predicted vs actual
Expected: 75m. Actual: approximately 10m, including plan/context review, temporary implementation, the focused verification run, and the base-tree premise audit. Stopped at the authoring defect; all partial edits removed.
