## Outcome
premise_failed

## Surprises / judgment calls
The scope fence omits squatch/watchdog.py, the owner of the route lookup and cost-basis attribution that the prior review requires this attempt to fix. WatchdogLLM.call resolves before awaiting its initial workspace sample, then calls CliClient.call without passing that resolution. A cooldown reset across that await permits the client to choose another provider. Passing the chosen Resolved through that boundary requires changing squatch/watchdog.py; an implicit routing cache or replacement watchdog in a fenced module would be a shim around the unfenced owner. Stopped without changing implementation files or committing.

The canonical plan already specifies attempt-granularity failover (section 6: "Failover granularity is the attempt, never mid-run"). The prior suggestion to retry another provider within the same call is not a new criterion and cannot override that rule. The plan's status was checked before any implementation edit; the concrete authoring defect is the missing watchdog owner in the fence.

## Dead ends
Reproduced the prior watchdog finding using the exact providers.py and timers.py sources from 9f2c01ac1818ec35316fb8a63f97fdecb1d84eea, loaded in memory through the Git seam, with the current WatchdogLLM. Armed Codex's cooldown, let the watchdog resolve Claude, advanced the injected clock through expiry during its initial sample, and invoked the client. The actual subprocess and result identity were codex/x-med, but watchdog._basis recorded {('claude', 'c-med'): 1.0}. The journal recorded timer_armed followed by timer_fired. No repository file was changed by this reproduction.

Verification on untouched base 15569c195f478b5021fc7a3e856903de5c94da2c:
- uv run pytest -q: exit 0; 1332 passed in 85.52 seconds.
- uv run pytest tests/test_provider_cooldown_failover.py tests/test_providers.py tests/test_restart_timers.py tests/test_stages.py tests/test_serve.py tests/test_merge.py tests/test_mergequeue.py tests/test_daemon_composition.py -q: exit 4; the new test_provider_cooldown_failover.py does not exist on the base. No implementation was attempted after establishing the scope blocker.

Paved road: include squatch/watchdog.py in the authoring fence so one resolved candidate can be shared explicitly by watchdog accounting and the CLI invocation, while preserving attempt-granularity failover and adding the cooldown-boundary regression in the already-fenced direct suite.

## Second problems filed
None. The full untouched-base suite is green; the historical pre-existing failures do not reproduce on this base.

## Resolved engine/model
OpenAI / GPT-6 (Codex); exact serving model identifier not exposed.

## Predicted vs actual
Expected: 75 minutes. Actual: approximately 10 minutes for contract inspection, prior-finding reproduction, and untouched-base verification; stopped on the scope authoring defect.
