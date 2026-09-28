---
verdict: snag
reviewed_sha: 7e71b0d86eb395ced1042fc45801027f148cb597
produced_by_spec_version: '1.0'
produced_at_sha: 7e71b0d86eb395ced1042fc45801027f148cb597
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The cooldown failover logic, the single restart-session Timers lifetime and the shared-payload migration look correct, and the checks are green. One regression: removing the guarded Registry construction from `_triage_pass` means a registry ConfigError on `squatch triage` now crashes the process instead of producing its Refusal and paved road.

## Findings
- correctness_review at squatch/daemon.py:367: Before this diff, `_triage_pass` wrapped `Registry(config)` in `try/except ConfigError` and raised `Refusal("config: ...", "fix the named provider or routing row in config.yaml")`. The diff deletes that handler. `Registry(config)` now runs inside the `providers` lambda of `compose_daemon_restart`, when `restart_session` is entered under the lock. `Registry.__init__` still raises ConfigError for provider and routing findings (providers.py `raise ConfigError(source, findings)`). `_locked` only turns GitError into a Refusal, and `_config` only covers `load()`. So a routing or provider row that passes `load()` but fails `Registry` validation now surfaces as an uncaught ConfigError traceback from `triage`, and from `drain`/`serve` at session entry, instead of the existing Refusal and paved road. That breaks the fail-closed/paved-road rule and changes an existing outcome the ticket says to keep. (paved road: Build the Registry where a ConfigError can still become the same Refusal. Either construct `Registry(config)` once in `_locked`/`_RestartRunner.session` before entering the restart session and convert ConfigError to `Refusal(f"config: {e}", "fix the named provider or routing row in config.yaml")`, or pass the prebuilt Registry into `compose_daemon_restart`. Add a test in tests/test_provider_cooldown_failover.py showing that `triage` with an invalid routing row still returns the Refusal.)
